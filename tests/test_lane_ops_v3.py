"""Tests for lane-ops v3 (arch-review-2 B1-B8, pre-Karen self-gate, WIP limit, NucBox-only Codex, capacity)."""
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "ops" / "lane-ops"
MINI = ROOT / "mini"
LW = MINI / "lane-wt-logs"
NUC = ROOT / "nucbox" / "nuc-tools"
SHARED = ROOT / "shared"
GATE = str(MINI / "bin" / "claim-gate.py")
HAS_ZSH = shutil.which("zsh") is not None
HAS_GIT = shutil.which("git") is not None


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_exe(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


def fake_gh(dirpath, payload):
    return write_exe(Path(dirpath) / "gh", "#!/usr/bin/env python3\nimport sys\nsys.stdout.write(%r)\n" % json.dumps(payload))


def jload(path):
    with open(path) as f:
        return json.load(f)


def jsave(path, j):
    with open(path, "w") as f:
        json.dump(j, f)


def iso(delta_s=0):
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=delta_s)).isoformat()


def wait_for(pred, timeout=20, step=0.1):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(step)
    return pred()


class GateBase(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.claims = os.path.join(self.d, "claims")
        os.makedirs(self.claims)
        self.env = dict(os.environ, CLAIM_GATE_CLAIMS=self.claims, CLAIM_GATE_GH=fake_gh(self.d, []))

    def cg(self, *args):
        r = subprocess.run([sys.executable, GATE, *args], capture_output=True, text=True, env=self.env, timeout=60)
        return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])

    def claim(self, owner, work="w1", title="fix thing one", lease="900", *extra):
        return self.cg("claim", "--repo", "o/r", "--work-id", work, "--title", title, "--owner", owner, "--lease-s", lease, *extra)

    def lapse(self, path, seconds=901):
        j = jload(path)
        j["heartbeat"] = iso(-seconds)
        jsave(path, j)


class ClaimGateB1StaleRelease(GateBase):
    """B1: a late release from a lapsed lane must never hide another lane's live claim."""

    def test_a_claims_lapses_b_claims_a_releases_c_must_skip(self):
        rc, a = self.claim("lane-a")
        self.assertEqual(rc, 0)
        self.lapse(a["claim"])
        rc, b = self.claim("lane-b")
        self.assertEqual(rc, 0, "A's lease lapsed, so B may claim")
        before = Path(a["claim"]).read_text()
        rc, out = self.cg("release", "--claim", a["claim"], "--owner", "lane-a", "--status", "FAILED")
        self.assertEqual(rc, 3, out)
        self.assertIn("lapsed", out["reason"])
        self.assertEqual(Path(a["claim"]).read_text(), before, "a refused release must not rewrite the file")
        rc, out = self.claim("lane-c")
        self.assertEqual(rc, 10, "B still holds the work: C must SKIP")
        self.assertEqual(out["by"], "lane-b")

    def test_even_if_a_lapsed_file_is_rewritten_its_mtime_cannot_hide_b(self):
        _, a = self.claim("lane-a")
        self.lapse(a["claim"])
        self.assertEqual(self.claim("lane-b")[0], 0)
        j = jload(a["claim"])
        j.update(status="DONE", released=iso())   # what the old `release --claim` did
        jsave(a["claim"], j)
        future = time.time() + 3600
        os.utime(a["claim"], (future, future))
        self.assertEqual(self.claim("lane-c")[0], 10)

    def test_legacy_release_by_lapsed_owner_cannot_hide_b(self):
        _, a = self.claim("lane-a")
        self.lapse(a["claim"])
        self.assertEqual(self.claim("lane-b")[0], 0)
        rc, _ = self.cg("release", "--repo", "o/r", "--work-id", "w1", "--owner", "lane-a")
        self.assertEqual(rc, 0)
        self.assertEqual(self.claim("lane-c")[0], 10)

    def test_newest_record_chosen_by_created_not_mtime(self):
        _, a = self.claim("lane-a")
        rc, _ = self.cg("release", "--claim", a["claim"], "--owner", "lane-a", "--status", "DONE")
        self.assertEqual(rc, 0)
        # an older RUNNING record of the same owner whose file was touched later must not come back to life
        old = jload(a["claim"])
        old.update(status="RUNNING", created=iso(-600), heartbeat=iso())
        p = os.path.join(self.claims, "gate-r-w1-lane-a-old.json")
        jsave(p, old)
        done = jload(a["claim"])
        done["created"] = iso(-60)
        jsave(a["claim"], done)
        future = time.time() + 3600
        os.utime(p, (future, future))
        self.assertEqual(self.claim("lane-b")[0], 0)

    def test_release_of_live_lease_still_frees_work(self):
        _, a = self.claim("lane-a")
        self.assertEqual(self.cg("release", "--claim", a["claim"], "--owner", "lane-a", "--status", "DONE")[0], 0)
        self.assertEqual(jload(a["claim"])["status"], "DONE")
        self.assertEqual(self.claim("lane-b")[0], 0)


class ClaimGateB8RenewAndCheck(GateBase):
    def test_renew_moves_expires_forward_by_ttl(self):
        _, a = self.claim("lane-a", "w1", "fix thing one", "900", "--ttl-min", "10")
        j = jload(a["claim"])
        self.assertEqual(j["ttl_min"], 10)
        j["expires"] = iso(60)
        jsave(a["claim"], j)
        rc, out = self.cg("renew", "--claim", a["claim"], "--owner", "lane-a")
        self.assertEqual(rc, 0, out)
        exp = dt.datetime.fromisoformat(jload(a["claim"])["expires"])
        left = (exp - dt.datetime.now(dt.timezone.utc)).total_seconds()
        self.assertGreater(left, 9 * 60)
        self.assertLessEqual(left, 10 * 60 + 5)

    def test_renew_never_extends_past_max_age(self):
        _, a = self.claim("lane-a", "w1", "fix thing one", "900", "--ttl-min", "300", "--max-age-min", "30")
        j = jload(a["claim"])
        self.assertEqual(j["max_age_s"], 1800)
        j["created"] = iso(-25 * 60)
        jsave(a["claim"], j)
        self.assertEqual(self.cg("renew", "--claim", a["claim"], "--owner", "lane-a")[0], 0)
        exp = dt.datetime.fromisoformat(jload(a["claim"])["expires"])
        self.assertLessEqual((exp - dt.datetime.now(dt.timezone.utc)).total_seconds(), 5 * 60 + 5)

    def test_renew_refused_after_max_age(self):
        _, a = self.claim("lane-a", "w1", "fix thing one", "900", "--max-age-min", "30")
        j = jload(a["claim"])
        j["created"] = iso(-31 * 60)
        jsave(a["claim"], j)
        rc, out = self.cg("renew", "--claim", a["claim"], "--owner", "lane-a")
        self.assertEqual(rc, 3)
        self.assertIn("max lease age", out["reason"])

    def test_default_max_age_from_env(self):
        self.env["LANE_MAX_AGE_MIN"] = "90"
        _, a = self.claim("lane-a")
        self.assertEqual(jload(a["claim"])["max_age_s"], 5400)

    def test_legacy_claim_ttl_inferred_from_created_and_expires(self):
        g = load(GATE, "claim_gate_v3")
        c = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        self.assertEqual(g.ttl_of({"created": c.isoformat(), "expires": (c + dt.timedelta(minutes=42)).isoformat()}),
                         dt.timedelta(minutes=42))
        self.assertEqual(g.ttl_of({"ttl_min": 7}), dt.timedelta(minutes=7))

    def test_check_fence(self):
        _, a = self.claim("lane-a")
        self.assertEqual(self.cg("check", "--claim", a["claim"], "--owner", "lane-a")[0], 0)
        self.assertEqual(self.cg("check", "--claim", a["claim"], "--owner", "lane-b")[0], 3)
        self.lapse(a["claim"])
        rc, out = self.cg("check", "--claim", a["claim"], "--owner", "lane-a")
        self.assertEqual(rc, 3)
        self.assertIn("lease", out["reason"])
        _, b = self.claim("lane-b", "w2", "other work")
        self.cg("release", "--claim", b["claim"], "--owner", "lane-b")
        self.assertEqual(self.cg("check", "--claim", b["claim"], "--owner", "lane-b")[0], 3)


@unittest.skipIf(shutil.which("bash") is None or shutil.which("pkill") is None, "bash + pkill required")
class LaneLeaseB2B3(GateBase):
    def setUp(self):
        super().setUp()
        self.env.update(CLAIM_GATE=GATE, LANE_LEASE_EVERY="1", LANE_RENEW_RETRIES="1", LANE_RENEW_RETRY_SLEEP="0")
        _, out = self.claim("lw", "w", "lease wrapper")
        self.claimf = out["claim"]
        self.sh = str(LW / "lane-lease.sh")

    def test_renew_failure_stops_the_lane(self):
        tag = "47.%d" % os.getpid()
        p = subprocess.Popen(["bash", self.sh, self.claimf, "lw", "--", "sleep", tag], env=self.env)
        self.assertTrue(wait_for(lambda: subprocess.run(["pgrep", "-f", "sleep " + tag], capture_output=True).returncode == 0, 10))
        j = jload(self.claimf)
        j["owner"] = "someone-else"   # every renew is now refused
        jsave(self.claimf, j)
        t0 = time.time()
        rc = p.wait(timeout=30)
        self.assertEqual(rc, 75, "a lost lease must stop the lane, not exit 0 and keep running")
        self.assertLess(time.time() - t0, 20)
        time.sleep(0.5)
        self.assertEqual(subprocess.run(["pgrep", "-f", "sleep " + tag], capture_output=True, text=True).stdout.strip(), "")

    def test_transient_renew_failure_is_retried(self):
        self.env.update(LANE_RENEW_RETRIES="3", LANE_RENEW_RETRY_SLEEP="1")
        gate = write_exe(Path(self.d, "flaky-gate.py"), textwrap.dedent(f"""\
            #!{sys.executable}
            import os, subprocess, sys
            n = os.path.join({self.d!r}, "renews")
            if sys.argv[1] == "renew":
                c = int(open(n).read()) if os.path.exists(n) else 0
                open(n, "w").write(str(c + 1))
                if c == 0:
                    sys.exit(3)
            sys.exit(subprocess.run([sys.executable, {GATE!r}] + sys.argv[1:]).returncode)
            """))
        self.env["CLAIM_GATE"] = gate
        r = subprocess.run(["bash", self.sh, self.claimf, "lw", "--", "sleep", "4"], env=self.env, timeout=60)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(jload(self.claimf)["status"], "DONE")

    def test_child_sees_claim_and_remote_is_beaten_and_stopped(self):
        home = Path(self.d, "home")
        log = Path(self.d, "remote.log")
        write_exe(home / "nuc-tools" / "lane-supervise.sh", f"#!/bin/bash\necho \"$1 $2\" >> {log}\n")
        env = dict(self.env, HOME=str(home), LANE_REMOTE_NAME="q-job1", LANE_REMOTE_SSH="bash -c")
        out = Path(self.d, "child.env")
        r = subprocess.run(["bash", self.sh, self.claimf, "lw", "--", "bash", "-c",
                            f"echo \"$LANE_CLAIM_FILE $LANE_CLAIM_OWNER\" > {out}; sleep 3"], env=env, timeout=60)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(out.read_text().split(), [self.claimf, "lw"])
        lines = log.read_text().splitlines()
        self.assertIn("beat q-job1", lines)
        self.assertEqual(lines[-1], "stop q-job1")

    def test_remote_stopped_on_signal_too(self):
        home = Path(self.d, "home")
        log = Path(self.d, "remote.log")
        write_exe(home / "nuc-tools" / "lane-supervise.sh", f"#!/bin/bash\necho \"$1 $2\" >> {log}\n")
        env = dict(self.env, HOME=str(home), LANE_REMOTE_NAME="q-job2", LANE_REMOTE_SSH="bash -c", LANE_LEASE_EVERY="300")
        p = subprocess.Popen(["bash", self.sh, self.claimf, "lw", "--", "sleep", "40.5"], env=env)
        time.sleep(1.5)
        p.send_signal(signal.SIGHUP)
        p.wait(timeout=30)
        self.assertEqual(jload(self.claimf)["status"], "FAILED")
        self.assertIn("stop q-job2", log.read_text())
        time.sleep(0.5)
        self.assertEqual(subprocess.run(["pgrep", "-f", "^sleep 300$"], capture_output=True, text=True).stdout.strip(), "",
                         "the renew loop's sleep must not outlive the wrapper")


@unittest.skipIf(shutil.which("setsid") is None, "setsid required")
class LaneSuperviseB3(unittest.TestCase):
    sh = str(NUC / "lane-supervise.sh")

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.env = dict(os.environ, LANE_SUPERVISE_DIR=self.d, LANE_SUPERVISE_CHECK="1", LANE_KILL_GRACE="2")

    def run_bg(self, name, lease, *cmd):
        return subprocess.Popen(["bash", self.sh, "run", name, str(lease), "--", *cmd], env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def ctl(self, act, name):
        return subprocess.run(["bash", self.sh, act, name], env=self.env, capture_output=True, text=True, timeout=30).returncode

    def gone(self, tag):
        return subprocess.run(["pgrep", "-f", tag], capture_output=True, text=True).stdout.strip() == ""

    def test_stop_kills_whole_group(self):
        tag = "61.%d" % os.getpid()
        p = self.run_bg("lane-a", 900, "bash", "-c", f"sleep {tag} & sleep {tag}1; wait")
        self.assertTrue(wait_for(lambda: Path(self.d, "lane-a.pgid").exists()))
        self.assertEqual(self.ctl("ok", "lane-a"), 0)
        self.assertEqual(self.ctl("stop", "lane-a"), 0)
        out, _ = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 143)
        self.assertTrue(wait_for(lambda: self.gone(f"sleep {tag}"), 10), "child and grandchild must both be killed")
        self.assertEqual(self.ctl("ok", "lane-a"), 3)
        self.assertEqual(self.ctl("beat", "lane-a"), 3, "a stopped lane can't be revived by a late beat")

    def test_lost_heartbeat_self_terminates(self):
        tag = "62.%d" % os.getpid()
        p = self.run_bg("lane-b", 2, "sleep", tag)
        out, _ = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 143)
        self.assertIn("heartbeat stale", out)
        self.assertTrue(self.gone(f"sleep {tag}"))

    def test_beats_keep_it_alive_and_exit_code_passes_through(self):
        p = self.run_bg("lane-c", 2, "bash", "-c", "sleep 5; exit 7")
        t0 = time.time()
        while p.poll() is None and time.time() - t0 < 30:
            self.ctl("beat", "lane-c")
            time.sleep(0.5)
        self.assertEqual(p.wait(timeout=5), 7)

    def test_ssh_hangup_kills_the_lane(self):
        tag = "63.%d" % os.getpid()
        p = self.run_bg("lane-d", 900, "sleep", tag)
        self.assertTrue(wait_for(lambda: Path(self.d, "lane-d.pgid").exists()))
        p.send_signal(signal.SIGHUP)
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 143)
        self.assertTrue(wait_for(lambda: self.gone(f"sleep {tag}"), 10))

    def test_child_gets_lane_name_and_hooks_path(self):
        p = self.run_bg("lane-e", 900, "bash", "-c", 'echo "N=$LANE_NAME H=$(git config core.hooksPath)"')
        out, _ = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertIn("N=lane-e", out)
        self.assertIn("H=" + str((NUC / "lane-hooks").resolve()), out)

    def test_bad_name_refused(self):
        self.assertEqual(self.ctl("stop", "../x"), 2)


@unittest.skipIf(not HAS_GIT, "git required")
class PrePushHookB6(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.origin = os.path.join(self.d, "origin.git")
        self.w = os.path.join(self.d, "w")
        g = lambda *a, cwd=None: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)
        self.g = g
        g("init", "-q", "--bare", "-b", "main", self.origin)
        g("clone", "-q", self.origin, self.w)
        for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
            g("config", k, v, cwd=self.w)
        Path(self.w, "tests").mkdir()
        Path(self.w, "tests/test_a.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertEqual(1, 1)\n")
        Path(self.w, "a.py").write_text("x = 1\n")
        g("add", "-A", cwd=self.w)
        g("commit", "-qm", "base", cwd=self.w)
        g("push", "-q", "origin", "HEAD:main", cwd=self.w)
        self.env = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.hooksPath",
                        GIT_CONFIG_VALUE_0=str(NUC / "lane-hooks"))
        self.env.pop("LANE_NAME", None)

    def push(self, *extra, env=None):
        return subprocess.run(["git", "push", *extra, "origin", "HEAD:main"], cwd=self.w, env=env or self.env, capture_output=True, text=True)

    def commit(self, path, text, msg):
        Path(self.w, path).write_text(text)
        self.g("commit", "-qam", msg, cwd=self.w)

    def test_normal_push_allowed(self):
        self.commit("a.py", "x = 2\n", "change")
        r = self.push()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_removed_assertion_refused_for_any_provider(self):
        self.commit("tests/test_a.py", "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        pass\n", "weaken")
        r = self.push()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("test-weakening policy", r.stderr)

    def test_skip_marker_refused(self):
        self.commit("tests/test_a.py", Path(self.w, "tests/test_a.py").read_text().replace("    def test_x", "    @unittest.skip('x')\n    def test_x"), "skip")
        self.assertNotEqual(self.push().returncode, 0)

    def test_force_push_refused(self):
        self.commit("a.py", "x = 3\n", "c1")
        self.assertEqual(self.push().returncode, 0)
        self.g("reset", "-q", "--hard", "HEAD~1", cwd=self.w)
        self.commit("a.py", "x = 4\n", "c2")
        r = self.push("--force")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("force-pushed", r.stderr)

    def test_fenced_when_lane_lost_its_lease(self):
        sup = os.path.join(self.d, "lanes")
        os.makedirs(sup)
        Path(sup, "lane-z.stop").write_text("")
        self.commit("a.py", "x = 5\n", "c")
        r = self.push(env=dict(self.env, LANE_NAME="lane-z", LANE_SUPERVISE_DIR=sup))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no longer holds its lease", r.stderr)

    def test_repo_hook_still_runs(self):
        write_exe(Path(self.w, ".git/hooks/pre-push"), "#!/bin/bash\necho repo-hook-ran >&2\nexit 1\n")
        self.commit("a.py", "x = 6\n", "c")
        r = self.push()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("repo-hook-ran", r.stderr)


class GatPolicyB6(unittest.TestCase):
    pol = load(NUC / "gat-policy.py", "gat_policy_v3")

    def diff(self, path, lines):
        return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1,1 +1,1 @@\n" + "\n".join(lines) + "\n"

    def test_missed_skip_patterns_now_refused(self):
        for line in ("+it.skipIf(isCI)('a', f)", "+describe.skipIf(x)('b', f)", "+test.skipIf(true)('c', f)",
                     "+test.runIf(false)('d', f)", "+pytestmark = pytest.mark.skip", "+np = pytest.importorskip('numpy')",
                     "+@unittest.expectedFailure", "+pytestmark = [pytest.mark.skipif(True, reason='x')]"):
            with self.subTest(line=line):
                self.assertTrue(self.pol.check(self.diff("tests/test_a.py", [line])), line)
                self.assertTrue(self.pol.check(self.diff("tests/test_a.py", [line]), push=True), line)

    def test_runner_config_in_package_json_refused(self):
        for line in ('+  "jest": {', '+    "testPathIgnorePatterns": ["slow"],', '+  "vitest": {', '+    "coverageThreshold": {}'):
            with self.subTest(line=line):
                self.assertTrue(self.pol.check(self.diff("package.json", [line])))

    def test_makefile_and_justfile_test_targets_refused(self):
        for path in ("Makefile", "justfile", "sub/GNUmakefile", "Taskfile.yml"):
            with self.subTest(path=path):
                self.assertTrue(self.pol.check(self.diff(path, ["-test:", "-\tpytest -q", "+test:", "+\ttrue"])))
        self.assertEqual(self.pol.check(self.diff("Makefile", ["-build:", "+build: deps"])), [])

    def test_ordinary_names_with_test_in_them_allowed(self):
        self.assertEqual(self.pol.check(self.diff("src/latest.ts", ["-a", "+b"])), [])
        self.assertEqual(self.pol.check(self.diff("src/contest.py", ["-a", "+b"])), [])

    def test_push_mode_allows_moves_but_not_removed_assertions(self):
        move = self.diff("tests/test_a.py", ["-if __name__ == '__main__':", "-    unittest.main()", "+class Late(unittest.TestCase):",
                                              "+    def test_y(self): self.assertTrue(1)", "+if __name__ == '__main__':", "+    unittest.main()"])
        self.assertTrue(self.pol.check(move), "strict mode keeps refusing any test-line deletion")
        self.assertEqual(self.pol.check(move, push=True), [])
        self.assertTrue(self.pol.check(self.diff("tests/test_a.py", ["-        self.assertEqual(a, 1)", "+        pass"]), push=True))
        self.assertTrue(self.pol.check(self.diff("tests/a.test.js", ["-  expect(x).toBe(1);"]), push=True))
        self.assertTrue(self.pol.check(self.diff("tests/test_a.py", ["-def test_gone():"]), push=True))

    def test_push_mode_ci_edits_warn_strict_refuses(self):
        d = self.diff(".github/workflows/t.yml", ["+      - run: pytest"])
        w = []
        self.assertEqual(self.pol.check(d, push=True, warnings=w), [])
        self.assertTrue(w)
        self.assertTrue(self.pol.check(d))

    def test_cli_push_flag(self):
        with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as f:
            f.write(self.diff(".github/workflows/t.yml", ["+x"]))
        self.addCleanup(os.unlink, f.name)
        r = subprocess.run([sys.executable, str(NUC / "gat-policy.py"), "--push", f.name], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("WARN", r.stdout)
        r = subprocess.run([sys.executable, str(NUC / "gat-policy.py"), f.name], capture_output=True, text=True)
        self.assertEqual(r.returncode, 3)

    def test_gat_numstat_rule_matches_test_paths_only(self):
        src = (NUC / "gemini-apply-test.sh").read_text()
        prog = re.search(r"awk '(\$2>0 && .*?)'; then", src).group(1)
        def refused(numstat):
            return subprocess.run(["awk", prog], input=numstat, text=True).returncode == 0
        self.assertFalse(refused("1\t1\tsrc/latest.ts\n"))
        self.assertFalse(refused("3\t0\ttests/test_new.py\n"))
        self.assertTrue(refused("1\t2\ttests/test_a.py\n"))
        self.assertTrue(refused("0\t1\tsrc/view.spec.ts\n"))
        self.assertTrue(refused("0\t1\tpkg/x_test.go\n"))


class ApplyEditsB7(unittest.TestCase):
    ae = load(NUC / "apply-edits.py", "apply_edits_v3")

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        Path(self.d, "a.py").write_text("x = 1\n")

    def blk(self, path, search, replace):
        return f"FILE: {path}\n<<<<<<< SEARCH\n{search}=======\n{replace}>>>>>>> REPLACE\n"

    def test_empty_search_on_existing_file_refused(self):
        with self.assertRaises(self.ae.EditError):
            self.ae.apply(self.blk("a.py", "", "x = 1\n"), self.d)
        self.assertEqual(Path(self.d, "a.py").read_text(), "x = 1\n")

    def test_empty_search_fills_an_empty_file(self):
        Path(self.d, "e.py").write_text("")
        self.ae.apply(self.blk("e.py", "", "y = 2\n"), self.d)
        self.assertEqual(Path(self.d, "e.py").read_text(), "y = 2\n")

    def test_git_dir_refused_in_any_case(self):
        for p in (".GIT/hooks/pre-commit", "sub/.Git/config", ".git/x"):
            with self.subTest(p=p), self.assertRaises(self.ae.EditError):
                self.ae.apply(self.blk(p, "", "x\n"), self.d)

    def test_write_is_atomic_and_keeps_mode(self):
        p = Path(self.d, "a.py")
        p.chmod(0o751)
        real = os.replace
        calls = []
        def boom(src, dst):
            calls.append((src, dst))
            raise OSError("disk full")
        self.ae.os.replace = boom
        try:
            with self.assertRaises(OSError):
                self.ae.apply(self.blk("a.py", "x = 1\n", "x = 2\n"), self.d)
        finally:
            self.ae.os.replace = real
        self.assertTrue(calls, "writes must go through os.replace")
        self.assertEqual(p.read_text(), "x = 1\n", "a failed write leaves the original intact")
        self.assertEqual(sorted(os.listdir(self.d)), ["a.py"], "no temp file left behind")
        self.ae.apply(self.blk("a.py", "x = 1\n", "x = 2\n"), self.d)
        self.assertEqual(p.read_text(), "x = 2\n")
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o751)


class CodexWinB8(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        old = time.time() - 3600
        def mk(name, version, age_old=True, works=True):
            exe = write_exe(Path(self.d, name, "codex.exe"),
                            f"#!/bin/bash\n[ \"$1\" = --version ] && {{ {'echo codex-cli ' + version if works else 'exit 1'}; exit 0; }}\necho RAN {name} \"$@\"\n")
            if age_old:
                os.utime(exe, (old, old)); os.utime(Path(self.d, name), (old, old))
        mk("aaaa", "0.163.0-alpha.10.2")
        mk("bbbb", "0.9.0")                 # newer-looking name, lower version
        mk("cccc", "0.170.0", age_old=False)  # just unpacked: must wait
        mk("dddd", "0.200.0", works=False)  # broken: --version fails
        self.env = dict(os.environ, CODEX_BIN_ROOT=self.d, CODEX_MIN_AGE_S="300")

    def test_picks_highest_settled_working_version(self):
        r = subprocess.run(["bash", str(NUC / "codex-win.sh"), "--which"], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(Path(self.d, "aaaa", "codex.exe")))

    def test_settled_update_wins_and_model_forced(self):
        old = time.time() - 3600
        os.utime(Path(self.d, "cccc", "codex.exe"), (old, old)); os.utime(Path(self.d, "cccc"), (old, old))
        r = subprocess.run(["bash", str(NUC / "codex-win.sh"), "exec", "hi"], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "RAN cccc -m gpt-6-astra exec hi")

    def test_none_usable_blocks(self):
        env = dict(self.env, CODEX_MIN_AGE_S="999999")
        r = subprocess.run(["bash", str(NUC / "codex-win.sh"), "--which"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("BLOCKER", r.stderr)


class FillQueueB5(unittest.TestCase):
    fq = load(LW / "fill-queue.py", "fill_queue_v3")

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.q = os.path.join(self.d, "fill.queue")

    def read(self):
        return Path(self.q).read_text().split()

    def test_add_remove_ready(self):
        self.fq.add(["a", "b", "a"], self.q)
        self.fq.add(["c"], self.q)
        self.assertEqual(self.read(), ["a", "b", "c"])
        self.fq.remove(["b"], self.q)
        self.assertEqual(self.fq.ready(self.q), ["a", "c"])

    def test_defer_keeps_job_then_drops_after_max(self):
        self.fq.add(["a", "b"], self.q)
        t = 1000.0
        self.assertEqual(self.fq.defer("a", 600, self.q, now=t), "DEFER")
        self.assertEqual(self.read(), ["a", "b"], "a refused lease must not drop the job")
        self.assertEqual(self.fq.ready(self.q, now=t + 10), ["b"])
        self.assertEqual(self.fq.ready(self.q, now=t + 601), ["a", "b"])
        for _ in range(self.fq.DEFER_MAX - 1):
            self.assertEqual(self.fq.defer("a", 600, self.q, now=t), "DEFER")
        self.assertEqual(self.fq.defer("a", 600, self.q, now=t), "DROP")
        self.assertEqual(self.read(), ["b"])

    def test_remove_clears_deferral(self):
        self.fq.add(["a"], self.q)
        self.fq.defer("a", 600, self.q)
        self.fq.remove(["a"], self.q)
        self.fq.add(["a"], self.q)
        self.assertEqual(self.fq.ready(self.q), ["a"])

    def test_concurrent_writers_lose_nothing(self):
        self.fq.add([f"keep{i}" for i in range(20)], self.q)
        code = textwrap.dedent(f"""
            import importlib.util, sys
            s = importlib.util.spec_from_file_location("fq", {str(LW / 'fill-queue.py')!r}); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
            who = sys.argv[1]
            for i in range(60):
                if who.startswith("add"): m.add([f"{{who}}-{{i}}"], {self.q!r})
                else: m.remove([f"keep{{i % 20}}"], {self.q!r}); m.add([f"keep{{i % 20}}"], {self.q!r})
            """)
        ps = [subprocess.Popen([sys.executable, "-c", code, w]) for w in ("add1", "churn", "add2")]
        for p in ps:
            self.assertEqual(p.wait(timeout=120), 0)
        got = set(self.read())
        want = {f"add1-{i}" for i in range(60)} | {f"add2-{i}" for i in range(60)} | {f"keep{i}" for i in range(20)}
        self.assertEqual(want - got, set(), "appends lost under concurrent rewrites")

    def test_cli(self):
        env = dict(os.environ, FILL_QUEUE=self.q)
        run = lambda *a: subprocess.run([sys.executable, str(LW / "fill-queue.py"), *a], env=env, capture_output=True, text=True)
        self.assertEqual(run("add", "x", "y").returncode, 0)
        self.assertEqual(run("defer", "x", "600").stdout.strip(), "DEFER x")
        self.assertEqual(run("ready").stdout.strip(), "y")
        self.assertEqual(run("bogus").returncode, 2)

    def test_fill_sh_never_rewrites_the_queue_directly(self):
        src = (LW / "fill.sh").read_text()
        self.assertNotRegex(src, r">\s*\$QFILE", "fill.sh must change fill.queue only through fill-queue.py")
        self.assertIn("q_defer $j", src)
        self.assertNotRegex(src, r"rest=\(\$\{pending:#\$j\}\)", "lease refusal must defer, not drop")


class AutoqueueV3(unittest.TestCase):
    def setUp(self):
        self.fa = load(LW / "fill-autoqueue.py", "fill_autoqueue_v3")
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.fa.LOGS = self.d
        self.fa.QUEUE = os.path.join(self.d, "fill.queue")
        self.fa.log = lambda m: None

    def drafts(self, n, repo="rupret007/webjam", author="rupret007"):
        return [{"number": i, "repository": {"nameWithOwner": repo}, "author": {"login": author}} for i in range(n)]

    def test_wip_limit_counts_trusted_priority_drafts(self):
        self.fa.gh_json = lambda args: self.drafts(16)
        self.assertFalse(self.fa.new_prs_allowed()[0])
        self.fa.gh_json = lambda args: self.drafts(15)
        self.assertTrue(self.fa.new_prs_allowed()[0], "the limit is 'more than 15'")
        self.fa.gh_json = lambda args: self.drafts(15) + self.drafts(30, repo="rupret007/not-a-priority-repo") + self.drafts(30, author="x")
        self.assertTrue(self.fa.new_prs_allowed()[0])
        self.fa.gh_json = lambda args: None
        self.assertFalse(self.fa.new_prs_allowed()[0], "unknown count holds new PRs (fail closed)")

    def test_default_limit_is_15(self):
        env = {k: v for k, v in os.environ.items() if k != "FILL_DRAFT_WIP_MAX"}
        r = subprocess.run([sys.executable, "-c", f"import importlib.util as u; s=u.spec_from_file_location('f', {str(LW / 'fill-autoqueue.py')!r}); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.DRAFT_WIP_MAX)"],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "15")

    def run_main(self, drafts):
        import io, contextlib
        fa = self.fa
        fa.read_queue = lambda: []
        fa.active_lane_jobs = lambda: set()
        fa.lease_ok = lambda j, p: True
        fa.is_parked = lambda j: False
        fa.issue_has_open_pr = lambda r, n: None
        fa.PRIORITY = [("webjam", "rupret007/webjam"), ("AdoptIQ", "rupret007/AdoptIQ")]
        fa.TARGET = 6
        fa.list_draft_prs = lambda repo: [{"number": 5, "title": "x", "headRefName": "b"}] if repo.endswith("AdoptIQ") else []
        fa.list_issues = lambda repo: [{"number": 9, "title": "feature"}]
        fa.gh_json = lambda args: drafts if args[:2] == ["search", "prs"] else [{"number": 1}]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fa.main()
        return json.loads(buf.getvalue().strip().splitlines()[-1])["added"]

    def test_over_limit_only_fixes_flow(self):
        added = self.run_main(self.drafts(16))
        self.assertIn("auto-AdoptIQ-pr5", added)
        self.assertFalse([a for a in added if "-iss" in a], added)

    def test_under_limit_new_prs_allowed(self):
        added = self.run_main(self.drafts(3))
        self.assertIn("auto-AdoptIQ-iss9", added)

    def test_write_queue_merges_with_current_queue(self):
        Path(self.fa.QUEUE).write_text("b c\n")   # fill.sh started a, gemini-feed appended c since autoqueue read
        new = self.fa.write_queue(["x", "a"], active={"a"})
        self.assertEqual(new, ["b", "c", "x"])
        self.assertEqual(Path(self.fa.QUEUE).read_text().split(), ["b", "c", "x"])

    def test_rules_require_pre_karen_check(self):
        self.assertIn("pre-karen-check.py", self.fa.RULES)
        self.assertIn("prekaren=", self.fa.RULES)


@unittest.skipIf(not HAS_ZSH, "zsh required")
class LaneRouteNucOnly(unittest.TestCase):
    def pick(self, host, nuc_ok):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        os.makedirs(os.path.join(home, "lane-wt", "logs"))
        shutil.copy(LW / "lane-route.conf", os.path.join(home, "lane-wt", "logs", "lane-route.conf"))
        script = (f". {LW / 'lane-route.sh'}; nuc_codex_ok(){{ return {0 if nuc_ok else 1}; }}; "
                  + (f"CODEX_HOST={host}; " if host is not None else "unset CODEX_HOST; ")
                  + "h=$(codex_host_pick); echo \"rc=$? h=$h\"")
        r = subprocess.run(["zsh", "-c", script], env=dict(os.environ, HOME=home), capture_output=True, text=True, timeout=30)
        return r.stdout.strip().splitlines()[-1]

    def test_no_mini_fallback(self):
        for host in ("auto", "nuc", None, "anything"):
            with self.subTest(host=host):
                self.assertEqual(self.pick(host, False), "rc=1 h=")
                self.assertEqual(self.pick(host, True), "rc=0 h=nuc")

    def test_explicit_mini_override_only(self):
        self.assertEqual(self.pick("mini", False), "rc=0 h=mini")

    def test_conf_is_nuc_only(self):
        conf = (LW / "lane-route.conf").read_text()
        self.assertRegex(conf, r"(?m)^CODEX_HOST=nuc\b")

    def test_fill_launch_has_no_mini_fallback(self):
        src = (LW / "fill.sh").read_text()
        self.assertNotIn("|| echo mini", src)
        self.assertIn("lane-supervise.sh run q-$j", src)


@unittest.skipIf(shutil.which("bash") is None, "bash required")
class MiniMemoryAdmission(unittest.TestCase):
    def mini_ok(self, level=1, free=55, swap_used=1000, hist=None, load="{ 3.0 3.0 3.0 }"):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "hist")
        if hist:
            Path(h).write_text("".join(f"{int(time.time()) - age} {mb}\n" for age, mb in hist))
        script = textwrap.dedent(f"""
            . {MINI / 'bin' / 'lane-guard.sh'}
            sysctl(){{ case "$2" in vm.loadavg) echo '{load}';; vm.swapusage) echo 'total = 4096.00M  used = {swap_used}.00M  free = 1.00M  (encrypted)';;
                       kern.memorystatus_vm_pressure_level) echo {level};; esac; }}
            memory_pressure(){{ echo 'System-wide memory free percentage: {free}%'; }}
            df(){{ echo 'Filesystem 1G-blocks Used Available'; echo '/dev/x 500 100 400'; }}
            MINI_SWAP_HIST={h}; mini_ok; echo "rc=$? $MINI_STATE"
            """)
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
        return r.stdout.strip().splitlines()[-1]

    def test_normal_admits(self):
        self.assertTrue(self.mini_ok().startswith("rc=0"), self.mini_ok())

    def test_pressure_warn_holds_even_at_low_load(self):
        self.assertTrue(self.mini_ok(level=2).startswith("rc=1"))
        self.assertTrue(self.mini_ok(level=4).startswith("rc=1"))

    def test_low_free_memory_holds(self):
        self.assertTrue(self.mini_ok(free=10).startswith("rc=1"))
        self.assertTrue(self.mini_ok(free=15).startswith("rc=0"))

    def test_fast_swap_growth_holds(self):
        self.assertTrue(self.mini_ok(swap_used=2000, hist=[(700, 1000)]).startswith("rc=1"))
        self.assertTrue(self.mini_ok(swap_used=1200, hist=[(700, 1000)]).startswith("rc=0"))

    def test_swap_percent_and_load_still_apply(self):
        self.assertTrue(self.mini_ok(swap_used=3500).startswith("rc=1"))
        self.assertTrue(self.mini_ok(load="{ 12.0 12.0 12.0 }").startswith("rc=1"))


@unittest.skipIf(shutil.which("bash") is None, "bash required")
class NucLaneB2B4B8(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.logs = self.d / "logs"; self.logs.mkdir()
        (self.logs / "n1.prompt").write_text("do the thing\n")
        shutil.copy(LW / "lane-lease.sh", self.logs / "lane-lease.sh")
        self.bin = self.d / "bin"; self.bin.mkdir()
        self.home = self.d / "home"
        self.state = self.d / "state"; self.state.mkdir()
        write_exe(self.home / "nuc-tools" / "lane-supervise.sh",
                  "#!/bin/bash\n[ \"$1\" = run ] || exit 0\nshift 3; [ \"$1\" = -- ] && shift; exec \"$@\"\n")
        write_exe(self.home / "nuc-tools" / "lane-run.sh", "#!/bin/bash\necho remote-cursor-ran\nexit 0\n")
        write_exe(self.home / "nuc-tools" / "lane-run-codex.sh", "#!/bin/bash\necho remote-codex-ran\nexit 0\n")
        self.guard = self.d / "guard.sh"
        self.guard.write_text("lane_preflight(){ return 0; }\ngh_throttle(){ :; }\n")
        self.claimf = self.d / "claim.json"
        self.gate = write_exe(self.bin / "gate.py", textwrap.dedent(f"""\
            #!{sys.executable}
            import json, os, sys
            st = {str(self.state)!r}
            cmd = sys.argv[1]
            open(os.path.join(st, "calls"), "a").write(cmd + "\\n")
            rc = os.environ.get("FAKE_CLAIM_RC", "0")
            if cmd == "claim":
                if rc == "3":
                    print(json.dumps({{"result": "BLOCKED"}})); sys.exit(3)
                open({str(self.claimf)!r}, "w").write("{{}}")
                print(json.dumps({{"result": "CLAIMED", "claim": {str(self.claimf)!r}}})); sys.exit(0)
            if cmd == "release":
                open(os.path.join(st, "release"), "w").write(sys.argv[sys.argv.index("--status") + 1])
            if cmd == "pre-pr":
                sys.exit(int(os.environ.get("FAKE_PREPR_RC", "0")))
            print(json.dumps({{"result": "OK"}}))
            """))
        write_exe(self.bin / "sleep", f"#!/bin/bash\necho \"$1\" >> {self.state}/sleeps\n")
        write_exe(self.bin / "git", "#!/bin/bash\n[ \"$1\" = ls-remote ] && { printf 'abc123\\trefs/heads/br\\n'; exit 0; }\nexit 0\n")
        write_exe(self.bin / "gh", textwrap.dedent("""\
            #!/bin/bash
            case "$1 $2" in
              "pr list") exit 0;;
              "api "*) echo "a.py"; exit 0;;
              "pr create") [ "${FAKE_CREATE:-ok}" = ok ] && { echo "https://github.com/rupret007/r/pull/42"; exit 0; }; echo "boom" >&2; exit 1;;
            esac
            exit 0
            """))
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", HOME=str(self.home), LANE_LOG_DIR=str(self.logs),
                        CLAIM_GATE=self.gate, LANE_GUARD=str(self.guard), NUC_SSH="bash -c", GH=str(self.bin / "gh"),
                        LANE_LEASE_EVERY="300")

    def run_lane(self, **env):
        r = subprocess.run(["bash", str(LW / "nuc-lane.sh"), "n1", "r", "br", "main", "w1"], env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=120)
        log = (self.logs / "n1.log").read_text()
        rel = (self.state / "release").read_text() if (self.state / "release").exists() else None
        return r.returncode, log, rel

    def test_blocked_claim_retries_briefly(self):
        rc, log, _ = self.run_lane(FAKE_CLAIM_RC="3")
        self.assertNotEqual(rc, 0)
        self.assertIn("CLAIM rc=3, not starting", log)
        calls = (self.state / "calls").read_text().split()
        self.assertEqual(calls.count("claim"), 3)
        sleeps = [int(x) for x in (self.state / "sleeps").read_text().split()]
        self.assertLessEqual(sum(sleeps), 120, "B8: no 30-minute wait inside a counted slot")

    def test_pr_create_failure_is_not_done(self):
        rc, log, rel = self.run_lane(FAKE_CREATE="fail")
        self.assertNotEqual(rc, 0)
        self.assertIn("BLOCKER pushed br@abc123 but gh pr create failed", log)
        self.assertNotIn("RESULT pr=", log)
        self.assertEqual(rel, "FAILED")

    def test_pre_pr_refusal_is_not_done(self):
        rc, log, rel = self.run_lane(FAKE_PREPR_RC="10")
        self.assertIn("pre-pr refused", log)
        self.assertNotIn("RESULT pr=", log)
        self.assertEqual(rel, "FAILED")

    def test_success_records_pr_and_releases_done(self):
        rc, log, rel = self.run_lane()
        self.assertEqual(rc, 0, log)
        self.assertIn("remote-cursor-ran", log)
        self.assertIn("RESULT pr=https://github.com/rupret007/r/pull/42 head=abc123", log)
        self.assertEqual(rel, "DONE")
        self.assertIn("check", (self.state / "calls").read_text().split(), "fence before PR create")

    def test_unreachable_nucbox_holds_no_mini_fallback(self):
        rc, log, rel = self.run_lane(NUC_SSH="false")
        self.assertNotEqual(rc, 0)
        self.assertIn("no Mini fallback", log)
        self.assertNotIn("remote-cursor-ran", log)
        self.assertNotIn("mini-fallback", log)
        self.assertEqual(rel, "FAILED")
        self.assertNotIn("codex exec", (LW / "nuc-lane.sh").read_text())
        self.assertNotIn("cursor-agent", (LW / "nuc-lane.sh").read_text())


@unittest.skipIf(not HAS_GIT or shutil.which("flock") is None, "git + flock required")
class RepoCacheAndTestSlots(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        (self.d / "gitconfig").write_text("[user]\n\temail = t@t\n\tname = t\n[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n")
        self.env = dict(os.environ, NUC_REPO_CACHE=str(self.d / "cache"), NUC_REPO_URL_BASE=f"file://{self.d / 'remote'}",
                        GIT_CONFIG_GLOBAL=str(self.d / "gitconfig"))
        self.g = lambda *a, cwd=None: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True, env=self.env).stdout.strip()
        base = self.d / "remote" / "o"; base.mkdir(parents=True)
        self.origin = base / "r.git"
        self.g("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.src = self.d / "src"
        self.g("clone", "-q", str(self.origin), str(self.src))
        (self.src / "f").write_text("1\n"); self.g("add", "f", cwd=self.src); self.g("commit", "-qm", "c1", cwd=self.src)
        self.g("push", "-q", "origin", "HEAD:main", cwd=self.src)
        self.g("push", "-q", "origin", "HEAD:refs/pull/7/head", cwd=self.src)

    def cache(self, dest, pr=None):
        r = subprocess.run(["bash", str(NUC / "nuc-repo-cache.sh"), "o/r", str(dest)] + ([str(pr)] if pr else []),
                           env=self.env, capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout.strip(), r.stderr

    def test_one_bare_clone_many_worktrees(self):
        rc, sha1, err = self.cache(self.d / "w1")
        self.assertEqual(rc, 0, err)
        (self.src / "f").write_text("2\n"); self.g("commit", "-qam", "c2", cwd=self.src); self.g("push", "-q", "origin", "HEAD:main", cwd=self.src)
        rc, sha2, err = self.cache(self.d / "w2")
        self.assertEqual(rc, 0, err)
        self.assertNotEqual(sha1, sha2, "cache must fetch new commits")
        self.assertEqual(len(list((self.d / "cache").glob("*.git"))), 1)
        rc, sha3, _ = self.cache(self.d / "w1")   # reuse a worktree path
        self.assertEqual((rc, sha3), (0, sha2))
        m = self.d / "cache" / "o__r.git"
        self.assertNotEqual(subprocess.run(["git", "-C", str(m), "config", "remote.origin.mirror"], capture_output=True, text=True).stdout.strip(), "true")

    def test_pr_head_and_explicit_push(self):
        rc, sha, err = self.cache(self.d / "wp", 7)
        self.assertEqual(rc, 0, err)
        w = self.d / "wp"
        (w / "f").write_text("pr\n")
        self.g("commit", "-qam", "pr fix", cwd=w)
        self.g("push", "-q", "origin", "HEAD:refs/heads/feature", cwd=w)
        self.assertEqual(self.g("--git-dir", str(self.origin), "rev-parse", "refs/heads/feature"), self.g("rev-parse", "HEAD", cwd=w))
        self.assertEqual(self.cache(self.d / "wx", 99)[0], 5)

    def test_test_slots_cap(self):
        env = dict(os.environ, NUC_TEST_SLOTS="1", NUC_TEST_SLOT_DIR=str(self.d / "slots"), NUC_TEST_SLOT_POLL="0.2")
        holder = subprocess.Popen(["bash", str(NUC / "nuc-test-slot.sh"), "--", "sleep", "3"], env=env)
        time.sleep(1)
        busy = subprocess.run(["bash", str(NUC / "nuc-test-slot.sh"), "true"], env=dict(env, NUC_TEST_SLOT_WAIT="0"), capture_output=True, text=True)
        self.assertEqual(busy.returncode, 75)
        later = subprocess.run(["bash", str(NUC / "nuc-test-slot.sh"), "bash", "-c", "exit 4"], env=dict(env, NUC_TEST_SLOT_WAIT="30"), timeout=60)
        self.assertEqual(later.returncode, 4)
        self.assertEqual(holder.wait(timeout=10), 0)

    def test_default_three_test_slots(self):
        self.assertEqual(re.search(r"NUC_TEST_SLOTS:-(\d+)", (NUC / "nuc-test-slot.sh").read_text()).group(1), "3")

    def test_gat_uses_cache_slots_and_fence(self):
        src = (NUC / "gemini-apply-test.sh").read_text()
        self.assertIn("nuc-repo-cache.sh", src)
        self.assertNotIn("gh repo clone", src)
        self.assertIn("nuc-test-slot.sh", src)
        self.assertIn("lane-supervise.sh ok", src)
        self.assertNotIn("gh repo clone", (NUC / "gemini-ctx.sh").read_text())


class PreKarenUnits(unittest.TestCase):
    pk = load(SHARED / "pre-karen-check.py", "pre_karen_check")

    def test_tests_after_main_detected(self):
        src = "import unittest\nclass A(unittest.TestCase):\n    def test_a(self): pass\nif __name__ == '__main__':\n    unittest.main()\n\nclass B(unittest.TestCase):\n    def test_b(self): pass\n"
        self.assertEqual(self.pk.py_tests_after_main(src), ["class B (line 7)"])
        self.assertEqual(self.pk.py_tests_after_main(src.split("\nclass B")[0]), [])

    def test_pytest_style_detection(self):
        self.assertTrue(self.pk.py_is_pytest_style("def test_x():\n    assert 1\n"))
        self.assertTrue(self.pk.py_is_pytest_style("import pytest\n@pytest.fixture\ndef f(): pass\n"))
        self.assertTrue(self.pk.py_is_pytest_style("class TestX:\n    def test_a(self): assert 1\n"))
        self.assertFalse(self.pk.py_is_pytest_style("import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"))

    def test_runner_and_coverage(self):
        cmds = ["nice -n 10 python -m unittest discover -s tests -v", "bash qa.sh"]
        self.assertEqual(self.pk.runners(cmds), {"unittest"})
        self.assertTrue(self.pk.unittest_covers(cmds, "tests/test_a.py"))
        self.assertFalse(self.pk.unittest_covers(cmds, "other/test_a.py"))
        self.assertFalse(self.pk.unittest_covers(["python -m unittest discover -s tests -p 'test_x*.py'"], "tests/test_a.py"))
        self.assertTrue(self.pk.unittest_covers(["python3 tests/test_board_meta.py"], "tests/test_board_meta.py"))
        self.assertTrue(self.pk.pytest_covers(["pytest -q tests"], "tests/test_a.py"))
        self.assertFalse(self.pk.pytest_covers(["pytest -q api/tests"], "tests/test_a.py"))

    def test_table_and_stale_body(self):
        body = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 |"
        self.assertTrue(self.pk.table_problems(body))
        self.assertEqual(self.pk.table_problems("| a | b |\n|---|---|\n| 1 | 2 |\n"), [])
        self.assertTrue(self.pk.STALE.search("No push, merge, PR from this lane"))
        self.assertTrue(self.pk.STALE.search("changes are local only"))
        self.assertIsNone(self.pk.STALE.search("CI green on head"))
        self.assertTrue(self.pk.ALLOWED_STALE.search("Do not merge before Karen gate."))

    def body_rows(self, body, head="d60bf99a816494dcea45b18760845a6e487d7617", ci="pass", mut=None, added=False, shas=()):
        import io, contextlib
        rep = self.pk.Report()
        with contextlib.redirect_stdout(io.StringIO()):
            self.pk.check_body(rep, body, head, None, ci, mut, added, repo_shas=set(shas))
        return rep

    def test_body_head_and_claims(self):
        self.assertEqual(self.body_rows("Head: d60bf99a, all good").verdict(), "PASS")
        self.assertEqual(self.body_rows("head is abcdef1 now").verdict(), "FAIL")
        self.assertEqual(self.body_rows("CI is green").verdict(), "PASS")
        self.assertEqual(self.body_rows("CI is green", ci="fail").verdict(), "FAIL")
        self.assertEqual(self.body_rows("All 5 mutations are caught", mut={"ran": 3, "unexcused": ["a.py:3"]}).verdict(), "FAIL")
        self.assertEqual(self.body_rows("All 5 mutations are caught", mut={"ran": 3, "unexcused": []}).verdict(), "PASS")
        rep = self.body_rows("No new tests.", added=True)
        self.assertIn("WARN", {r["level"] for r in rep.rows})
        self.assertEqual(self.body_rows("Do not merge before Karen gate.").verdict(), "PASS")
        self.assertEqual(self.body_rows("timeout at 10000000 ms").verdict(), "PASS")

    def test_mutants_and_counts(self):
        self.assertTrue(self.pk.mutants_for_line("    if a == b and c:"))
        self.assertTrue(self.pk.mutants_for_line("    limit = 900"))
        self.assertEqual(self.pk.mutants_for_line("import os"), [])
        self.assertEqual(self.pk.mutants_for_line("# a == b"), [])
        self.assertEqual(self.pk.count_py_tests("def test_a(): pass\nclass T:\n    def test_b(self): pass\n"), 2)
        self.assertEqual(self.pk.count_js_tests("it('a', f)\ntest('b', f)\nit.each([1])('c', f)\n"), 3)
        self.assertEqual(self.pk.equivalent_excused("Equivalent mutants: src/a.py:74 (equal times)\n\nOther"), {"src/a.py:74"})


@unittest.skipIf(not HAS_GIT, "git required")
class PreKarenLocalRun(unittest.TestCase):
    """End to end on a throwaway repo: the self-gate catches what Karen caught tonight."""

    def setUp(self):
        self.w = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.w, True)
        self.g = lambda *a: subprocess.run(["git", *a], cwd=self.w, check=True, capture_output=True, text=True).stdout.strip()
        self.g("init", "-q", "-b", "main")
        for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
            self.g("config", k, v)
        (self.w / ".github" / "workflows").mkdir(parents=True)
        (self.w / ".github/workflows/t.yml").write_text("jobs:\n  t:\n    steps:\n      - name: Run\n        run: python -m unittest discover -s tests -v\n")
        (self.w / "tests").mkdir()
        (self.w / "m.py").write_text("def ok(n):\n    return True\n")
        (self.w / "tests/test_m.py").write_text("import unittest\nimport m\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(m.ok(1000))\n\nif __name__ == '__main__':\n    unittest.main()\n")
        self.g("add", "-A"); self.g("commit", "-qm", "base")
        self.base = self.g("rev-parse", "HEAD")
        fd, self.body = tempfile.mkstemp(suffix=".md"); os.close(fd)
        self.addCleanup(os.unlink, self.body)

    def check(self, body=""):
        Path(self.body).write_text(body)
        r = subprocess.run([sys.executable, str(SHARED / "pre-karen-check.py"), "--local", "--workdir", str(self.w), "--base", self.base,
                            "--body-file", self.body, "--test-cmd", f"{sys.executable} -m unittest discover -s tests", "--mutants", "4"],
                           capture_output=True, text=True, timeout=300, env=dict(os.environ, PRE_KAREN_NO_SLOT="1"))
        return r.returncode, r.stdout

    def commit(self, files, msg="head"):
        for p, t in files.items():
            (self.w / p).write_text(t)
        self.g("add", "-A"); self.g("commit", "-qm", msg)

    def test_weak_test_leaves_surviving_mutant(self):
        self.commit({"m.py": "def ok(n):\n    return n >= 900\n",
                     "tests/test_m.py": "import unittest\nimport m\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(m.ok(1000))\n\nif __name__ == '__main__':\n    unittest.main()\n"})
        rc, out = self.check()
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"PRE-KAREN mutation FAIL: .*m\.py:2")

    def test_strong_tests_pass(self):
        self.commit({"m.py": "def ok(n):\n    return n >= 900\n",
                     "tests/test_m.py": "import unittest\nimport m\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(m.ok(1000))\n        self.assertTrue(m.ok(900))\n        self.assertFalse(m.ok(899))\n\nif __name__ == '__main__':\n    unittest.main()\n"})
        rc, out = self.check("Adds the 900 limit with boundary tests.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("PRE-KAREN RESULT PASS", out)

    def test_tests_after_main_block_fail(self):
        self.commit({"tests/test_m.py": (self.w / "tests/test_m.py").read_text() + "\nclass Late(unittest.TestCase):\n    def test_late(self):\n        self.assertTrue(m.ok(1000))\n"})
        rc, out = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("ci-collects FAIL", out)
        self.assertIn("class Late", out)

    def test_pytest_style_under_unittest_ci_fail(self):
        self.commit({"tests/test_p.py": "import m\n\ndef test_p():\n    assert m.ok(1000)\n"})
        rc, out = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("pytest-style tests, but CI runs no pytest", out)

    def test_weakened_test_and_stale_body_fail(self):
        self.commit({"tests/test_m.py": "import unittest\nimport m\n\nclass T(unittest.TestCase):\n    pass\n\nif __name__ == '__main__':\n    unittest.main()\n"})
        rc, out = self.check("No push, merge, PR: local only.\n| a | b |\n|---|---|\n| 1 |")
        self.assertEqual(rc, 1)
        self.assertIn("no-weakening FAIL", out)
        self.assertIn("1 tests at base, 0 at head", out)
        self.assertIn("body FAIL: stale note", out)
        self.assertIn("body FAIL: truncated table", out)


@unittest.skipIf(shutil.which("bash") is None, "bash required")
class KarenRequestGate(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.n = self.d / "n"
        write_exe(self.d / "gh", f"#!/bin/bash\nc=$(cat {self.n} 2>/dev/null || echo 0); echo $((c+1)) > {self.n}\n"
                                 "if [ -n \"$MOVE\" ] && [ \"$c\" -ge 1 ]; then echo bbbbbbbbbbbbbbbbbbbb; else echo aaaaaaaaaaaaaaaaaaaa; fi\n")
        self.chk = write_exe(self.d / "chk.sh", "#!/bin/bash\nj=''; while [ $# -gt 0 ]; do [ \"$1\" = --json ] && j=$2; shift; done\n"
                                                "echo \"PRE-KAREN mutation $V: x\"; echo \"PRE-KAREN RESULT $V head=a\"; echo '{}' > $j\n"
                                                "case $V in PASS) exit 0;; FAIL) exit 1;; *) exit 2;; esac\n")
        self.env = dict(os.environ, GH=str(self.d / "gh"), NUC_SSH="bash -c", PREKAREN_REMOTE=f"bash {self.chk}",
                        PREKAREN_DIR=str(self.d / "out"))

    def req(self, **env):
        return subprocess.run(["bash", str(MINI / "bin" / "karen-request.sh"), "o/r", "7"], env=dict(self.env, **env),
                              capture_output=True, text=True, timeout=60)

    def test_pass_allows_request_and_stores_report(self):
        r = self.req(V="PASS")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("KAREN_REQUEST_OK o/r#7 head=aaaaaaaaaaaaaaaaaaaa", r.stdout)
        self.assertTrue(list((self.d / "out").glob("o__r__pr7__aaaaaaaaaaaa.log")))

    def test_fail_blocks_request(self):
        r = self.req(V="FAIL")
        self.assertEqual(r.returncode, 1)
        self.assertIn("KAREN_REQUEST_BLOCKED", r.stdout)
        self.assertIn("PRE-KAREN mutation FAIL", r.stdout)

    def test_pending_waits(self):
        self.assertEqual(self.req(V="PENDING").returncode, 2)

    def test_head_moving_during_check_waits(self):
        r = self.req(V="PASS", MOVE="1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("head moved", r.stdout)

    def test_bad_args(self):
        r = subprocess.run(["bash", str(MINI / "bin" / "karen-request.sh"), "o/r", "x;rm"], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 64)


if __name__ == "__main__":
    unittest.main()

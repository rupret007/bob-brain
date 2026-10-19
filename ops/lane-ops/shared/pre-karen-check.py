#!/usr/bin/env python3
"""pre-karen-check.py: the mechanical first round of a Karen gate, run by the lane BEFORE it asks Karen.

lane-ops v3 (arch-review-2 item 1). Tonight's Karen FAILs were mostly mechanical: tests CI never ran
(`unittest.main()` mid-file), surviving mutations on changed lines, and stale or truncated PR bodies. This script
catches those in minutes so Karen's rounds go to real review. Karen keeps the final say; a PASS here is only the
ticket to ask her.

  pre-karen-check.py --repo OWNER/R --pr N [--workdir DIR] [--test-cmd CMD] [--mutants 8] [--no-mutation]
                     [--json OUT]
  pre-karen-check.py --local --workdir DIR --base REF [--head REF] [--body-file F] [--test-cmd CMD] ...
                     (no GitHub: for tests and dry runs; the CI-status check is skipped)

Checks (each prints `PRE-KAREN <check> PASS|WARN|FAIL|PENDING: ...`):
  ci-collects    every new/changed test is collected by what CI actually runs: no test class/function defined
                 after `if __name__ == "__main__":`, no pytest-style tests under a unittest-only CI, the file sits
                 under a discover root / listed path, JS test files are reachable from the `test` script
  mutation       quick mutation smoke on the changed source lines (operator/constant flips, one at a time, tests
                 re-run each time). A survivor FAILs unless the PR body lists it under "Equivalent mutants:"
                 as path:line
  body           the PR body matches the head: no stale "no push / not pushed / local only" notes, no truncated
                 tables, no head/tip SHA other than the real head, no "CI green" / "mutations caught" claims the
                 evidence doesn't back, no "no new tests" when tests were added
  no-weakening   gat-policy.py --push on base...head (skip markers, removed assertions, runner config) and no test
                 file ends up with fewer tests than at base
  head-checks    every check on the head SHA has finished green (FAIL on a failure, PENDING while running)
Exit: 0 PASS (WARNs allowed), 1 FAIL, 2 PENDING or could not run.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GH = os.environ.get("GH", "gh")
TEST_PATH = re.compile(r"(^|/)(tests?|specs?|__tests__|e2e)/|(^|/)test_[^/]*\.py$|_test\.py$|\.(test|spec)\.[cm]?[jt]sx?$", re.I)
PY_TEST = re.compile(r"(^|/)test_[^/]*\.py$|_test\.py$")
JS_TEST = re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$")
SRC_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx")


class Report:
    def __init__(self):
        self.rows = []

    def add(self, check, level, msg):
        self.rows.append({"check": check, "level": level, "msg": msg})
        print(f"PRE-KAREN {check} {level}: {msg}")

    def verdict(self):
        lv = {r["level"] for r in self.rows}
        return "FAIL" if "FAIL" in lv else "PENDING" if "PENDING" in lv else "PASS"


def sh(cmd, cwd=None, timeout=120, check=False, env=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {r.stderr.strip()[:300]}")
    return r


# ---------------------------------------------------------------- diff parsing
def changed_lines(diff_text):
    """{path: set(new-side line numbers added or changed)} for a unified diff (git diff -U0 works best)."""
    out, path, ln = {}, None, 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            p = raw[4:].split("\t")[0].strip()
            path = None if p == "/dev/null" else re.sub(r"^b/", "", p)
            continue
        if raw.startswith("--- ") or raw.startswith("diff ") or raw.startswith("index "):
            continue
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", raw)
        if m:
            ln = int(m.group(1))
            continue
        if path is None:
            continue
        if raw.startswith("+"):
            out.setdefault(path, set()).add(ln)
            ln += 1
        elif raw.startswith("-"):
            out.setdefault(path, set())
        elif raw.startswith(" "):
            ln += 1
    return out


# ---------------------------------------------------------------- ci-collects
def py_tests_after_main(src):
    """Names of tests defined after a top-level `if __name__ == "__main__":` block (never run by `python file.py`)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    main_line = None
    late = []
    for node in tree.body:
        if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test) and "__main__" in ast.unparse(node.test):
            main_line = node.lineno if main_line is None else main_line
            continue
        if main_line is None:
            continue
        if isinstance(node, ast.ClassDef) and any(isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) and b.name.startswith("test") for b in node.body):
            late.append(f"class {node.name} (line {node.lineno})")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            late.append(f"def {node.name} (line {node.lineno})")
    return late


def py_is_pytest_style(src):
    """True when the file has tests only pytest collects: module-level test functions, fixtures, parametrize."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for d in getattr(node, "decorator_list", []):
                if re.search(r"pytest\.(fixture|mark\.parametrize)", ast.unparse(d)):
                    return True
        if isinstance(node, ast.ClassDef) and not any("TestCase" in ast.unparse(b) for b in node.bases):
            if node.name.startswith("Test") and any(isinstance(b, ast.FunctionDef) and b.name.startswith("test") for b in node.body):
                return True
    return False


def count_py_tests(src):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            n += 1
    return n


def count_js_tests(src):
    return len(re.findall(r"(?<![\w.])(?:it|test)(?:\.each\([^)]*\))?\s*\(\s*['\"`]", src))


def ci_commands(root):
    """Shell commands CI runs: workflow `run:` lines plus the lines of repo scripts they call (one level)."""
    cmds = []
    wf = Path(root, ".github", "workflows")
    for f in sorted(list(wf.glob("*.yml")) + list(wf.glob("*.yaml"))) if wf.is_dir() else []:
        text = f.read_text(errors="replace")
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = re.match(r"^(\s*)(?:-\s*)?run:\s*(.*)$", lines[i])
            if m:
                ind, first = len(m.group(1)), m.group(2).strip()
                if first in ("|", ">", "|-", ">-", "|+"):
                    i += 1
                    while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > ind):
                        if lines[i].strip():
                            cmds.append(lines[i].strip())
                        i += 1
                    continue
                cmds.append(first)
            i += 1
    extra = []
    for c in cmds:
        for tok in re.findall(r"(?:^|\s)(?:bash\s+|sh\s+|zsh\s+|\./)?([\w./-]+\.sh)\b", c):
            p = Path(root, tok.lstrip("./"))
            if p.is_file():
                extra += [l.strip() for l in p.read_text(errors="replace").splitlines() if l.strip() and not l.strip().startswith("#")]
    return cmds + extra


def runners(cmds):
    r = set()
    for c in cmds:
        if re.search(r"\bpytest\b", c):
            r.add("pytest")
        if re.search(r"\bunittest\b", c) or re.search(r"\bpython[0-9.]*\s+(-\S+\s+)*[\w./-]+\.py\b", c):
            r.add("unittest")
        if re.search(r"\b(npm|pnpm|yarn)\s+(run\s+)?test\b|\bnpx\s+(vitest|jest|playwright)\b|\bnode\s+--test\b", c):
            r.add("js")
    return r


def unittest_covers(cmds, path):
    """True when some CI command would run the unittest file at `path` (discover root/pattern, module, or file)."""
    mod = path[:-3].replace("/", ".")
    name = os.path.basename(path)
    for c in cmds:
        if "unittest" in c and "discover" in c:
            try:
                toks = shlex.split(c)
            except ValueError:
                toks = c.split()
            start, pat = ".", "test*.py"
            for i, t in enumerate(toks):
                if t in ("-s", "--start-directory") and i + 1 < len(toks):
                    start = toks[i + 1]
                if t in ("-p", "--pattern") and i + 1 < len(toks):
                    pat = toks[i + 1]
            pos = [t for t in toks[toks.index("discover") + 1:] if not t.startswith("-")] if "discover" in toks else []
            if pos and start == "." and not any(t in ("-s", "--start-directory") for t in toks):
                start = pos[0]
                if len(pos) > 1:
                    pat = pos[1]
            start = start.rstrip("/") or "."
            if (start == "." or path.startswith(start + "/")) and fnmatch.fnmatch(name, pat):
                return True
        if re.search(rf"(?<![\w/.-]){re.escape(path)}\b", c) or re.search(rf"\bunittest\b.*\b{re.escape(mod)}\b", c):
            return True
    return False


def pytest_covers(cmds, path):
    for c in cmds:
        if not re.search(r"\bpytest\b", c):
            continue
        args = [t for t in re.split(r"\s+", c.split("pytest", 1)[1]) if t and not t.startswith("-")]
        paths = [a for a in args if "/" in a or a.endswith(".py") or os.path.isdir(a)]
        if not paths or any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in paths):
            return True
    return False


def js_test_reachable(root, path):
    try:
        pkg = json.loads(Path(root, "package.json").read_text())
    except (OSError, ValueError):
        return None
    script = ((pkg.get("scripts") or {}).get("test") or "")
    toks = [t for t in re.split(r"\s+", script) if re.search(r"\.[cm]?[jt]sx?$|[*]", t)]
    if not toks:
        return True   # vitest/jest/playwright defaults glob for *.test.* / *.spec.*
    return any(fnmatch.fnmatch(path, t.strip("'\"")) or t.strip("'\"") == path for t in toks)


def check_ci_collects(rep, root, changed, base_files):
    tests = [p for p in changed if TEST_PATH.search(p) and Path(root, p).is_file()]
    if not tests:
        rep.add("ci-collects", "PASS", "no new or changed test files")
        return
    cmds = ci_commands(root)
    run = runners(cmds)
    bad = 0
    for p in tests:
        src = Path(root, p).read_text(errors="replace")
        if p.endswith(".py"):
            late = py_tests_after_main(src)
            if late:
                bad += 1
                rep.add("ci-collects", "FAIL", f"{p}: {', '.join(late)} defined after `if __name__ == \"__main__\":`; "
                        "running the file directly never collects them. Move the __main__ block to the end")
            if py_is_pytest_style(src) and "pytest" not in run:
                bad += 1
                rep.add("ci-collects", "FAIL", f"{p}: pytest-style tests, but CI runs no pytest ({sorted(run) or 'no runner found'})")
            if not PY_TEST.search(p):
                continue
            if "pytest" in run and pytest_covers(cmds, p):
                continue
            if "unittest" in run and unittest_covers(cmds, p):
                continue
            bad += 1
            rep.add("ci-collects", "FAIL", f"{p}: no CI command collects this file ({len(cmds)} CI commands read)")
        elif JS_TEST.search(p):
            ok = js_test_reachable(root, p)
            if ok is False:
                bad += 1
                rep.add("ci-collects", "FAIL", f"{p}: package.json `test` lists explicit files and this one is not among them")
            elif ok is None:
                rep.add("ci-collects", "WARN", f"{p}: no package.json; could not confirm CI runs it")
            if "js" not in run:
                rep.add("ci-collects", "WARN", f"{p}: no npm/pnpm/vitest/jest/node --test step found in CI")
    if not bad:
        rep.add("ci-collects", "PASS", f"{len(tests)} test file(s) reachable from CI ({', '.join(sorted(run)) or 'n/a'})")


# ---------------------------------------------------------------- mutation smoke
MUTATIONS = [
    (r"==", "!="), (r"!=", "=="), (r"<=", ">"), (r">=", "<"), (r"(?<![<>=!-])<(?![<=])", ">="), (r"(?<![<>=!-])>(?![>=])", "<="),
    (r"\band\b", "or"), (r"\bor\b", "and"), (r"&&", "||"), (r"\|\|", "&&"),
    (r"\bTrue\b", "False"), (r"\bFalse\b", "True"), (r"\btrue\b", "false"), (r"\bfalse\b", "true"),
    (r"\bnot\s+", ""), (r"(?<![\w.])(\d+)(?![\w.])", None),
]


def mutants_for_line(line):
    code = re.split(r"\s#|//", line, 1)[0]
    if not code.strip() or re.match(r"\s*(import|from|export|#|//|\*|def |class |function |return\s*;?$)", code) or code.strip().startswith(("'", '"')):
        return []
    out = []
    for pat, rep in MUTATIONS:
        for m in re.finditer(pat, code):
            if re.search(r"['\"`]", code[:m.start()]) and code[:m.start()].count('"') % 2 == 1:
                continue
            if rep is None:
                n = int(m.group(1))
                new = code[:m.start()] + str(n + 1) + code[m.end():]
            else:
                new = code[:m.start()] + rep + code[m.end():]
            out.append((f"{m.group(0).strip() or m.group(0)!r} -> {rep if rep is not None else int(m.group(1)) + 1}", new + line[len(code):]))
            break
    return out


def equivalent_excused(body):
    m = re.search(r"Equivalent mutants?:\s*(.+?)(?:\n\s*\n|\Z)", body or "", re.S | re.I)
    return set(re.findall(r"([\w./-]+:\d+)", m.group(1))) if m else set()


def detect_test_cmd(root):
    if Path(root, "package.json").is_file():
        return "npm test --silent"
    cmds = ci_commands(root)
    for c in cmds:
        if re.search(r"\bpython[0-9.]*\s+-m\s+(unittest|pytest)\b", c) or re.match(r"\s*pytest\b", c):
            return re.sub(r"^nice\s+-n\s+\d+\s+", "", c)
    if Path(root, "tests").is_dir():
        return f"{shlex.quote(sys.executable)} -m unittest discover -s tests"
    return None


def run_tests(root, cmd, timeout):
    slot = Path(os.path.expanduser("~/nuc-tools/nuc-test-slot.sh"))
    full = (["bash", str(slot), "bash", "-c", cmd] if slot.is_file() and os.environ.get("PRE_KAREN_NO_SLOT") != "1"
            else ["bash", "-c", cmd])
    try:
        r = subprocess.run(full, cwd=root, capture_output=True, text=True, timeout=timeout, env=dict(os.environ, CI="1"))
        return r.returncode, (r.stdout + r.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def check_mutation(rep, root, changed, body, test_cmd, limit, timeout):
    src = [(p, sorted(ls)) for p, ls in changed.items() if ls and p.endswith(SRC_EXT) and not TEST_PATH.search(p) and Path(root, p).is_file()]
    other = sorted(p for p, ls in changed.items() if ls and not p.endswith(SRC_EXT) and not TEST_PATH.search(p)
                   and re.search(r"\.(sh|bash|zsh)$", p))
    if other:
        rep.add("mutation", "WARN", f"shell scripts are not mutated ({len(other)} changed); Karen should mutate them by hand")
    if not src:
        rep.add("mutation", "PASS", "no changed source lines to mutate")
        return {"ran": 0, "survivors": []}
    cmd = test_cmd or detect_test_cmd(root)
    if not cmd:
        rep.add("mutation", "FAIL", "changed source but no test command found (pass --test-cmd)")
        return {"ran": 0, "survivors": []}
    rc, tail = run_tests(root, cmd, timeout)
    if rc != 0:
        rep.add("mutation", "FAIL", f"tests fail at head before mutating (rc={rc}): {tail.strip()[-300:]}")
        return {"ran": 0, "survivors": [], "baseline_rc": rc}
    cands = []
    for p, lines in src:
        text = Path(root, p).read_text(errors="replace").split("\n")
        for ln in lines:
            if 1 <= ln <= len(text):
                for desc, new in mutants_for_line(text[ln - 1]):
                    cands.append((p, ln, desc, new))
    if not cands:
        rep.add("mutation", "PASS", "changed lines have no mutable operators/constants")
        return {"ran": 0, "survivors": []}
    # spread the budget across files and lines
    picked, seen = [], set()
    for c in cands:
        if (c[0], c[1]) not in seen and len(picked) < limit:
            picked.append(c); seen.add((c[0], c[1]))
    for c in cands:
        if len(picked) >= limit:
            break
        if c not in picked:
            picked.append(c)
    excused = equivalent_excused(body)
    survivors, killed = [], 0
    for p, ln, desc, new in picked:
        f = Path(root, p)
        orig = f.read_text(errors="surrogateescape")
        lines = orig.split("\n")
        lines[ln - 1] = new
        try:
            f.write_text("\n".join(lines), errors="surrogateescape")
            rc, _ = run_tests(root, cmd, timeout)
        finally:
            f.write_text(orig, errors="surrogateescape")
        if rc == 0:
            survivors.append(f"{p}:{ln} ({desc})")
        else:
            killed += 1
    real = [s for s in survivors if s.split(" ")[0] not in excused]
    if real:
        rep.add("mutation", "FAIL", f"{len(real)}/{len(picked)} mutants survived: {'; '.join(real)}. Add tests that kill them, or list "
                "true equivalents under 'Equivalent mutants:' in the PR body")
    else:
        rep.add("mutation", "PASS", f"{killed}/{len(picked)} mutants killed" + (f", {len(survivors)} excused as equivalent" if survivors else ""))
    return {"ran": len(picked), "killed": killed, "survivors": survivors, "unexcused": real}


# ---------------------------------------------------------------- body
STALE = re.compile(r"\bno (push|merge|PR)\b[^.\n]*|\bnot (yet )?pushed\b|\bnothing (was )?pushed\b|\blocal(ly)?[- ]only\b|"
                   r"\buncommitted\b|\bnot committed\b|\b(PR|body) (to be|will be) (written|updated)\b|\bTODO\b.{0,20}\bbody\b", re.I)
ALLOWED_STALE = re.compile(r"do not merge|don'?t merge|no merge (until|before|without)|not for merge", re.I)


def table_problems(body):
    probs = []
    lines = (body or "").splitlines()
    i = 0
    while i < len(lines) - 1:
        h, sep = lines[i].strip(), lines[i + 1].strip()
        if h.startswith("|") and re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$", sep):
            cols = len([c for c in h.strip("|").split("|")])
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                row = lines[j].strip()
                n = len(row.strip("|").split("|")) if row.endswith("|") else len(row.lstrip("|").split("|"))
                if not row.endswith("|") or n != cols:
                    probs.append(f"table row {j + 1} has {n} cells{'' if row.endswith('|') else ' and no closing |'} (header has {cols}): {row[:60]!r}")
                j += 1
            i = j
            continue
        i += 1
    return probs


def check_body(rep, body, head, commits, ci_state, mutation, tests_added, repo_shas=None):
    body = body or ""
    bad = 0
    for line in body.splitlines():
        m = STALE.search(line)
        if m and not ALLOWED_STALE.search(line):
            bad += 1
            rep.add("body", "FAIL", f"stale note: {line.strip()[:100]!r}")
    for p in table_problems(body):
        bad += 1
        rep.add("body", "FAIL", f"truncated table: {p}")
    for m in re.finditer(r"\b(head|tip|HEAD|Head|Tip|at)\b\s*(?:is|=|:|@|SHA)?\s*`?([0-9a-f]{7,40})\b`?", body):
        label, sha = m.group(1).lower(), m.group(2)
        if not re.search(r"[a-f]", sha) or not head or head.startswith(sha):
            continue
        in_pr = any(s.startswith(sha) or sha.startswith(s) for s in (repo_shas or ()))
        if label in ("head", "tip"):
            bad += 1
            rep.add("body", "FAIL", f"body names {m.group(0).strip()!r} but the head is {head[:12]}")
        elif not in_pr:
            rep.add("body", "WARN", f"body mentions {m.group(0).strip()!r}, which is not a commit of this PR")
    if re.search(r"\bCI\b[^.\n]{0,20}\b(green|passe[sd]|passing)\b|\ball (required )?checks? (are )?(green|pass)", body, re.I):
        if ci_state not in ("pass", None):
            bad += 1
            rep.add("body", "FAIL", f"body claims CI is green but head checks are {ci_state}")
    if re.search(r"\bmutat\w*\b[^.\n]{0,40}\b(caught|killed|pass)", body, re.I):
        if mutation is not None and (mutation.get("unexcused") or not mutation.get("ran")):
            bad += 1
            rep.add("body", "FAIL", "body claims mutations are caught, but this run " +
                    ("had survivors" if mutation.get("unexcused") else "ran no mutants"))
    if tests_added and re.search(r"\bno new tests\b", body, re.I):
        rep.add("body", "WARN", "body says 'no new tests' but the diff adds tests")
    if not bad:
        rep.add("body", "PASS", "no stale notes, truncated tables or unbacked claims")


# ---------------------------------------------------------------- no weakening
def find_policy():
    for p in (HERE / "gat-policy.py", HERE.parent / "nucbox" / "nuc-tools" / "gat-policy.py", Path(os.path.expanduser("~/nuc-tools/gat-policy.py"))):
        if p.is_file():
            return p
    return None


def check_weakening(rep, root, base, head, diff_text, changed):
    bad = 0
    pol = find_policy()
    if pol is None:
        rep.add("no-weakening", "FAIL", "gat-policy.py not found; cannot check (fail closed)")
        return
    with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False) as f:
        f.write(diff_text)
    try:
        r = sh([sys.executable, str(pol), "--push", f.name])
    finally:
        os.unlink(f.name)
    for line in r.stdout.splitlines():
        if "refuses" in line:
            bad += 1
            rep.add("no-weakening", "FAIL", line.split(":", 1)[1].strip())
        elif "WARN" in line:
            rep.add("no-weakening", "WARN", line.split(":", 1)[1].strip())
    for p in changed:
        if not TEST_PATH.search(p):
            continue
        old = sh(["git", "show", f"{base}:{p}"], cwd=root)
        if old.returncode != 0:
            continue
        new_path = Path(root, p)
        new = new_path.read_text(errors="replace") if new_path.is_file() else ""
        cnt = count_py_tests if p.endswith(".py") else count_js_tests
        a, b = cnt(old.stdout), cnt(new)
        if a is not None and b is not None and b < a:
            bad += 1
            rep.add("no-weakening", "FAIL", f"{p}: {a} tests at base, {b} at head")
    if not bad:
        rep.add("no-weakening", "PASS", "no skip markers, removed assertions or lost tests")


# ---------------------------------------------------------------- head checks
def check_head(rep, repo, pr, head):
    r = sh([GH, "pr", "checks", str(pr), "-R", repo, "--json", "name,bucket,state"], timeout=90)
    try:
        rows = json.loads(r.stdout or "[]")
    except ValueError:
        rows = None
    if not isinstance(rows, list):
        rep.add("head-checks", "PENDING", f"could not read checks: {r.stderr.strip()[:200]}")
        return "unknown"
    if not rows:
        rep.add("head-checks", "PENDING", f"no checks reported for {head[:12]} yet")
        return "none"
    fail = [x["name"] for x in rows if x.get("bucket") in ("fail", "cancel")]
    pend = [x["name"] for x in rows if x.get("bucket") == "pending"]
    if fail:
        rep.add("head-checks", "FAIL", f"failing on {head[:12]}: {', '.join(fail)}")
        return "fail"
    if pend:
        rep.add("head-checks", "PENDING", f"still running on {head[:12]}: {', '.join(pend)}")
        return "pending"
    rep.add("head-checks", "PASS", f"{len(rows)} checks green/skipped on {head[:12]}")
    return "pass"


# ---------------------------------------------------------------- main
def prepare_workdir(repo, pr, head, base_ref, workdir):
    if workdir:
        got = sh(["git", "rev-parse", "HEAD"], cwd=workdir).stdout.strip()
        if got != head:
            raise RuntimeError(f"workdir is at {got[:12]}, PR head is {head[:12]}")
        return workdir, None
    tmp = tempfile.mkdtemp(prefix="pre-karen-")
    cache = Path(os.path.expanduser("~/nuc-tools/nuc-repo-cache.sh"))
    if cache.is_file():
        sh(["bash", str(cache), repo, tmp + "/w", str(pr)], timeout=900, check=True)
        w = tmp + "/w"
    else:
        w = tmp + "/w"
        sh(["git", "clone", "-q", "--filter=blob:none", f"https://github.com/{repo}.git", w], timeout=900, check=True)
        sh(["git", "fetch", "-q", "origin", f"+refs/pull/{pr}/head:refs/remotes/origin/pr/{pr}"], cwd=w, timeout=300, check=True)
        sh(["git", "checkout", "-q", "--detach", head], cwd=w, check=True)
    sh(["git", "fetch", "-q", "origin", base_ref], cwd=w, timeout=300)
    return w, tmp


def main(argv=None):
    ap = argparse.ArgumentParser(description="mechanical pre-Karen gate")
    ap.add_argument("--repo"); ap.add_argument("--pr", type=int)
    ap.add_argument("--local", action="store_true"); ap.add_argument("--workdir")
    ap.add_argument("--base"); ap.add_argument("--head"); ap.add_argument("--body-file")
    ap.add_argument("--test-cmd"); ap.add_argument("--mutants", type=int, default=int(os.environ.get("PRE_KAREN_MUTANTS", "8")))
    ap.add_argument("--mutant-timeout", type=int, default=int(os.environ.get("PRE_KAREN_MUTANT_TIMEOUT", "600")))
    ap.add_argument("--no-mutation", action="store_true"); ap.add_argument("--json")
    a = ap.parse_args(argv)
    rep = Report()
    tmp = None
    try:
        if a.local:
            if not (a.workdir and a.base):
                ap.error("--local needs --workdir and --base")
            root = a.workdir
            head = sh(["git", "rev-parse", a.head or "HEAD"], cwd=root, check=True).stdout.strip()
            body = Path(a.body_file).read_text() if a.body_file else ""
            base = sh(["git", "merge-base", a.base, head], cwd=root, check=True).stdout.strip()
            ci_state = None
        else:
            if not (a.repo and a.pr):
                ap.error("--repo and --pr required (or --local)")
            j = json.loads(sh([GH, "pr", "view", str(a.pr), "-R", a.repo, "--json", "headRefOid,baseRefName,body"], check=True).stdout)
            head, body = j["headRefOid"], j.get("body") or ""
            root, tmp = prepare_workdir(a.repo, a.pr, head, j["baseRefName"], a.workdir)
            b = sh(["git", "merge-base", f"origin/{j['baseRefName']}", head], cwd=root)
            if b.returncode != 0:
                b = sh(["git", "merge-base", j["baseRefName"], head], cwd=root, check=True)
            base = b.stdout.strip()
            ci_state = check_head(rep, a.repo, a.pr, head)
        diff_text = sh(["git", "diff", "-U0", base, head], cwd=root, check=True).stdout
        full_diff = sh(["git", "diff", base, head], cwd=root, check=True).stdout
        changed = changed_lines(diff_text)
        base_files = set(sh(["git", "ls-tree", "-r", "--name-only", base], cwd=root).stdout.split())
        check_ci_collects(rep, root, changed, base_files)
        mut = None if a.no_mutation else check_mutation(rep, root, changed, body, a.test_cmd, a.mutants, a.mutant_timeout)
        if a.no_mutation:
            rep.add("mutation", "WARN", "skipped (--no-mutation)")
        tests_added = any(TEST_PATH.search(p) and ls for p, ls in changed.items())
        shas = set(sh(["git", "rev-list", "--abbrev=7", "--abbrev-commit", f"{base}..{head}"], cwd=root).stdout.split())
        check_body(rep, body, head, None, ci_state if not a.local else None, mut, tests_added, repo_shas=shas)
        check_weakening(rep, root, base, head, full_diff, changed)
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError, KeyError) as e:
        rep.add("run", "PENDING", f"could not complete: {e}")
        head = locals().get("head", "")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    v = rep.verdict()
    print(f"PRE-KAREN RESULT {v} head={locals().get('head', '')}")
    if a.json:
        Path(a.json).write_text(json.dumps({"verdict": v, "head": locals().get("head", ""), "repo": a.repo, "pr": a.pr,
                                            "rows": rep.rows}, indent=2) + "\n")
    return {"PASS": 0, "FAIL": 1}.get(v, 2)


if __name__ == "__main__":
    sys.exit(main())

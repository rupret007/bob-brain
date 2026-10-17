import asyncio
import datetime as dt
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from webbob import ownership as gate
from webbob.ownership_adapter import Executor, Ticket, ANDREA_RELEASE


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patch = patch.object(gate, "CLAIMS", str(self.root))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.clock = dt.datetime(2026, 10, 16, tzinfo=dt.timezone.utc)
        self.time_patch = patch.object(gate, "now", side_effect=lambda: self.clock)
        self.time_patch.start()
        self.addCleanup(self.time_patch.stop)
        self.repo = "rupret007/bob-brain"
        self.resource = "repo:rupret007/bob-brain/services/publish.py"

    def claim(self, owner="webbob", work="one", resource=None, ttl=240):
        return gate.Gate(owner).claim(self.repo, work, [resource or self.resource], ttl, "draft/same")

    def args(self, row):
        return row["repo"], row["work_id"], row["token"], row["fence"]

    def test_all_six_documented_identities_and_unknown_identity(self):
        docs = (Path(__file__).resolve().parents[1] / "docs/ownership-gate.md").read_text()
        for owner in ("bob", "grok", "webbob", "andrea", "karen", "codex"):
            self.assertIn(f"`{owner}`", docs)
            row = self.claim(owner, owner, "browser:" + owner)
            self.assertEqual(row["owner"], owner)
        with self.assertRaises(gate.GateError):
            gate.Gate("unknown")

    def test_observer_cannot_read_owner_branch_title_or_job_metadata(self):
        row = gate.Gate("webbob").claim(self.repo, "private-job", [self.resource],
                                       branch="draft/private", title="Private job title")
        owner_view = gate.Gate("webbob").get_owner(self.resource)
        self.assertEqual(owner_view["branch"], "draft/private")
        self.assertEqual(owner_view["title"], "Private job title")
        for owner in ("bob", "grok", "andrea", "karen", "codex"):
            observed = gate.Gate(owner).get_owner(self.resource)
            self.assertEqual(observed, {key: row[key] for key in ("owner", "status", "expires", "fence")})

    def test_missing_relative_and_explicit_root_configuration(self):
        code = """
from webbob.ownership import Gate, GateError
try:
    assert Gate('bob').get_owner('browser:empty') is None
except GateError:
    raise SystemExit(3)
"""
        env = {k: v for k, v in os.environ.items() if k not in {"CLAIM_GATE_ROOT", "CLAIM_GATE_CLAIMS"}}
        claims = self.root / "coord" / "claims"
        claims.mkdir(parents=True)
        for config, expected in (({}, 3), ({"CLAIM_GATE_ROOT": "relative"}, 3),
                                 ({"CLAIM_GATE_CLAIMS": "relative"}, 3),
                                 ({"CLAIM_GATE_ROOT": str(self.root)}, 0),
                                 ({"CLAIM_GATE_CLAIMS": str(claims)}, 0)):
            with self.subTest(config=config):
                result = subprocess.run([sys.executable, "-c", code], env=env | config,
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode, expected)

    def test_simultaneous_four_bots_yield_one_owner_and_unrelated_work_proceeds(self):
        barrier = threading.Barrier(4)
        outcomes = []
        def claim(owner):
            barrier.wait()
            try:
                outcomes.append((owner, self.claim(owner, owner)))
            except gate.GateError:
                outcomes.append((owner, None))
        threads = [threading.Thread(target=claim, args=(owner,)) for owner in ("webbob", "bob", "andrea", "karen")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sum(row is not None for _, row in outcomes), 1)
        self.assertEqual(self.claim("bob", "other", "browser:unrelated")["owner"], "bob")

    def test_same_branch_does_not_exempt_other_owner(self):
        self.claim()
        with self.assertRaises(gate.GateError):
            self.claim("bob", "different")

    def test_token_bound_renewal_preserves_fence_and_extends_lease(self):
        row = self.claim(ttl=10)
        self.clock += dt.timedelta(seconds=9)
        renewed = gate.Gate("webbob").renew(*self.args(row), ttl=240)
        self.clock += dt.timedelta(seconds=2)
        self.assertEqual(gate.Gate("bob").get_owner(self.resource)["fence"], row["fence"])
        self.assertGreater(renewed["expires"], row["expires"])
        self.assertNotIn("token", renewed)
        self.assertNotIn("token_hash", renewed)

    def test_release_requires_current_owner_token_and_generation(self):
        row = self.claim()
        for owner, token, fence in [("bob", row["token"], row["fence"]),
                                     ("webbob", "forged", row["fence"]),
                                     ("webbob", row["token"], row["fence"] + 1)]:
            with self.assertRaises(gate.GateError):
                gate.Gate(owner).release(self.repo, "one", token, fence)
        gate.Gate("webbob").release(*self.args(row))
        self.assertIsNone(gate.Gate("bob").get_owner(self.resource))
        with self.assertRaises(gate.GateError):
            gate.Gate("webbob").release(*self.args(row))
        next_row = self.claim("bob", "next")
        self.assertGreater(next_row["fence"], row["fence"])

    def test_expired_owner_cannot_publish_renew_or_release_after_takeover(self):
        ex = Executor("webbob")
        ticket = ex.reserve(self.repo, "one", [self.resource], ttl=1)
        self.clock += dt.timedelta(seconds=1)
        next_row = self.claim("bob", "two")
        effect = self.root / "published"
        for call in [lambda: ex.protected(ticket, self.resource, lambda: effect.write_text("bad")),
                     lambda: ex.renew(ticket), lambda: ex.release(ticket)]:
            with self.assertRaises(gate.GateError):
                call()
        self.assertFalse(effect.exists())
        self.assertGreater(next_row["fence"], ticket.fence)

    def test_valid_publish_and_resource_fencing(self):
        ex = Executor("webbob")
        ticket = ex.reserve(self.repo, "one", [self.resource])
        self.assertEqual(ex.protected(ticket, self.resource, lambda: "published"), "published")
        with self.assertRaises(gate.GateError):
            ex.protected(ticket, "outbound:email", lambda: self.fail("effect admitted"))

    def test_parent_resource_excludes_children(self):
        self.claim(resource="repo:rupret007/bob-brain")
        with self.assertRaises(gate.GateError):
            self.claim("bob", "child")

    def test_corrupt_and_unreadable_records_fail_closed(self):
        row = self.claim()
        bad = self.root / "broken.json"
        for data in ["{", "[]", '{}', '{"owner": "bob"}']:
            bad.write_text(data)
            for operation in [lambda: gate.Gate("bob").get_owner("browser:unclaimed"),
                              lambda: self.claim("bob", "other", "browser:unclaimed"),
                              lambda: gate.Gate("webbob").release(*self.args(row))]:
                with self.assertRaises(gate.GateError):
                    operation()
        bad.unlink()
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                gate.Gate("bob").get_owner("browser:unclaimed")
        with patch.object(Path, "iterdir", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                gate.Gate("bob").get_owner("browser:unclaimed")

    def test_record_order_is_independent_of_mtime(self):
        row = self.claim()
        first = next(self.root.glob("*.json"))
        gate.Gate("webbob").release(*self.args(row))
        os.utime(first, (9999999999, 9999999999))
        self.assertIsNone(gate.Gate("bob").get_owner(self.resource))

    def test_legacy_active_claim_and_failed_gh_check_block_acquisition(self):
        (self.root / "legacy.json").write_text(json.dumps({
            "repo": self.repo, "work_id": "legacy", "owner": "bob", "status": "RUNNING",
            "files": [], "expires": (self.clock + dt.timedelta(hours=1)).isoformat()}))
        with self.assertRaises(gate.GateError):
            self.claim()
        def fail():
            raise RuntimeError("GitHub unavailable")
        with self.assertRaises(RuntimeError):
            gate.Gate("webbob").claim(self.repo, "other", ["browser:other"], check=fail)
        self.assertIsNone(gate.Gate("webbob").get_owner("browser:other"))

    def test_invalid_resource_ttl_and_andrea_version_denied(self):
        for resource in ["repo:a/../b", "repo:a//b", "repo:a/", " repo:a", "url:https://example.org"]:
            with self.assertRaises(gate.GateError):
                self.claim(resource=resource)
        for ttl in [-1, 0, True, 14401]:
            with self.assertRaises(gate.GateError):
                self.claim(ttl=ttl)
        with self.assertRaises(gate.GateError):
            Executor("andrea", "unknown")
        with self.assertRaises(gate.GateError):
            Executor("andrea", "83623dd8")
        pin = json.loads((Path(__file__).resolve().parents[1] / "release/andrea-bridge.json").read_text())
        self.assertEqual(ANDREA_RELEASE, pin["sha"])
        self.assertEqual(Executor("andrea", ANDREA_RELEASE).gate.owner, "andrea")

    def test_malformed_legacy_records_deny_even_when_expired_or_released(self):
        valid = dict(repo=self.repo, work_id="legacy", owner="bob", status="RELEASED",
                     expires=(self.clock - dt.timedelta(hours=1)).isoformat(), files=[])
        for mutation in [dict(work_id=42), dict(repo=None), dict(files=[None]),
                         dict(files=["../escape"]), dict(created="bad"),
                         dict(resources=["browser:hidden"])]:
            with self.subTest(mutation=mutation):
                (self.root / "legacy.json").write_text(json.dumps(valid | mutation))
                with self.assertRaises((gate.GateError, ValueError)):
                    gate.Gate("webbob").get_owner("browser:unclaimed")

    def test_legacy_write_after_migration_cannot_be_hidden_by_sequence(self):
        row = self.claim()
        self.clock += dt.timedelta(seconds=1)
        (self.root / "legacy.json").write_text(json.dumps(dict(
            repo=self.repo, work_id="one", owner="bob", status="RUNNING", files=[],
            created=self.clock.isoformat(), expires=(self.clock + dt.timedelta(hours=1)).isoformat())))
        with self.assertRaises(gate.GateError):
            with gate.Gate("webbob").execution(*self.args(row), self.resource):
                self.fail("legacy takeover admitted publication")
        with self.assertRaises(gate.GateError):
            gate.Gate("bob").get_owner("browser:unclaimed")


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_protocol_owner_binding_and_fail_closed_error(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, CLAIM_GATE_CLAIMS=tmp, WEBBOB_BOT_ID="webbob")
            params = StdioServerParameters(command=sys.executable, args=["-m", "webbob.ownership_mcp"], env=env)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    self.assertEqual({t.name for t in tools}, {"claim", "renew", "release", "get_owner"})
                    self.assertNotIn("owner", next(t for t in tools if t.name == "claim").inputSchema["properties"])
                    result = await session.call_tool("claim", {"repo": "a/b", "work_id": "one", "resources": ["browser:one"]})
                    self.assertFalse(result.isError)
                    row = json.loads(result.content[0].text)
                    self.assertEqual(row["owner"], "webbob")
                    result = await session.call_tool("release", {"repo": "a/b", "work_id": "one", "token": "wrong", "fence": row["fence"]})
                    self.assertTrue(result.isError)
                    Path(tmp, "corrupt.json").write_text("{")
                    result = await session.call_tool("get_owner", {"resource": "browser:empty"})
                    self.assertTrue(result.isError)


if __name__ == "__main__":
    unittest.main()

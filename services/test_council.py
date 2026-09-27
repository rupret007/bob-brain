#!/usr/bin/env python3
"""Council and draft failure tests: no live models, API calls, jobs or messages."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import api
import conductor_pass
import council
import drafts
import state


class CouncilTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bob-council-test-")
        self.root = Path(self.temp.name)
        self.events = []
        self.event_patch = patch.object(council, "append_event", side_effect=lambda name, event: self.events.append(event))
        self.event_patch.start()

    def tearDown(self):
        self.event_patch.stop()
        self.temp.cleanup()

    def run_council(self, ask):
        with patch.object(council, "ask", side_effect=ask):
            return council.run("Review services and rank three fixes", [], self.root)

    def test_all_members_propose_cross_critique_then_synthesize(self):
        calls = []
        def answer(member, prompt):
            calls.append((member, prompt))
            if "ROLE: critic." in prompt:
                for other in council.MEMBERS:
                    marker = "## " + council.LABELS[other] + " proposal"
                    self.assertEqual(marker in prompt, other != member)
            return "Recommendation from " + member + ": preserve independent services and validate drafts."
        status, transcript, answered = self.run_council(answer)
        self.assertEqual(status, "synthesized")
        self.assertEqual(set(answered), set(council.MEMBERS))
        self.assertEqual(len(calls), 2 * len(council.MEMBERS) + 1)
        self.assertEqual(len(self.events), len(calls))
        self.assertIn("**Participation:** full", transcript.read_text())
        self.assertTrue(transcript.with_suffix(".context.txt").exists())

    def test_one_member_is_not_a_council(self):
        def answer(member, prompt):
            if member != "codex":
                raise RuntimeError("provider unavailable")
            self.assertIn("ROLE: proposer.", prompt)
            return "One real proposal cannot be called a multi-model decision."
        status, transcript, answered = self.run_council(answer)
        self.assertEqual(status, "NO-QUORUM")
        self.assertEqual(answered, ["codex"])
        self.assertNotIn("## Synthesized plan", transcript.read_text())

    def test_failed_critique_quorum_does_not_synthesize(self):
        def answer(member, prompt):
            if "ROLE: critic." in prompt:
                raise RuntimeError("critique transport failed")
            self.assertNotIn("ROLE: synthesizer.", prompt)
            return "An independent proposal with concrete file evidence."
        status, transcript, _ = self.run_council(answer)
        self.assertEqual(status, "NO-CRITIQUE-QUORUM")
        self.assertIn("critique transport failed", transcript.read_text())

    def test_synthesizer_fallback_is_recorded(self):
        def answer(member, prompt):
            if member in ("cursor", "claude") and "ROLE: synthesizer." in prompt:
                raise RuntimeError("synthesizer unavailable")
            return "Evidence-backed recommendation for durable isolated services."
        status, transcript, _ = self.run_council(answer)
        self.assertEqual(status, "synthesized")
        self.assertIn("by Codex", transcript.read_text())
        self.assertIn("synthesize claude ok=False", transcript.read_text())

    def test_completed_answers_survive_interrupted_later_phase(self):
        original = council.fan_out
        def fan_out(members, phase, build, ledger):
            if phase == "critique":
                raise KeyboardInterrupt()
            return original(members, phase, build, ledger)
        with patch.object(council, "fan_out", side_effect=fan_out), self.assertRaises(KeyboardInterrupt):
            self.run_council(lambda *args: "Persist this completed answer before the next call.")
        transcript, = self.root.glob("*.md")
        self.assertEqual(transcript.read_text().count("Persist this completed answer"), len(council.MEMBERS))
        self.assertIn("RUNNING", transcript.read_text())  # never invent a completion

    def test_api_members_use_shared_metered_lanes(self):
        with patch("lanes.ask", return_value="Metered response with evidence") as ask:
            for member in ("minimax", "gemini", "cursor"):
                council.ask(member, "Review this evidence")
        self.assertEqual([call.args[0] for call in ask.call_args_list], ["minimax", "gemini", "cursor"])
        self.assertTrue(all(call.kwargs["purpose"] == "council" for call in ask.call_args_list))

    def test_context_is_complete_or_fails_visibly_before_any_call(self):
        services = self.root / "services"
        services.mkdir()
        (services / "long.py").write_text("x" * 200)
        build = self.root / "BUILD-SERVICES.md"
        build.write_text("Required design contract")
        with patch.object(council, "MAX_CONTEXT", 100), patch.object(council, "ask") as ask:
            status, transcript, _ = council.run("Review", [services, build], self.root / "out")
        self.assertEqual(status, "CONTEXT-FAILED")
        self.assertIn("context exceeds", transcript.read_text())
        ask.assert_not_called()
        self.assertIn("Required design contract", council.load_context([services, build]))

    def test_question_evidence_answers_and_errors_are_redacted(self):
        secret = "credential-value-for-redaction-test"
        evidence = self.root / "evidence.md"
        evidence.write_text(secret)
        def answer(member, prompt):
            self.assertNotIn(secret, prompt)
            if member == "gemini":
                raise RuntimeError("failure " + secret)
            return "A usable recommendation with " + secret
        with patch.object(council, "_SECRETS", {secret}), patch.object(council, "ask", side_effect=answer):
            _, transcript, _ = council.run(secret, [evidence], self.root)
        self.assertNotIn(secret, transcript.read_text())
        self.assertNotIn(secret, transcript.with_suffix(".context.txt").read_text())
        self.assertNotIn(secret, json.dumps(self.events))


class DraftTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bob-draft-test-")
        self.root = Path(self.temp.name)
        self.live = self.root / "live"
        self.services = self.live / "conductor/services"
        self.services.mkdir(parents=True)
        (self.services / "worker.py").write_text("VALUE = 'live'\n")
        (self.services / "test_services.py").write_text("# trusted baseline test\n")
        (self.live / "conductor/keys.env").write_text("SECRET=never-copy\n")
        self.folder = self.root / "pass"
        self.workspace, self.baseline = drafts.prepare(self.live, self.folder)

    def tearDown(self):
        self.temp.cleanup()

    def test_invalid_draft_cannot_touch_live_services_or_erase_concurrent_edit(self):
        (self.workspace / "conductor/services/worker.py").write_text("def broken(:\n")
        (self.services / "worker.py").write_text("VALUE = 'concurrent live edit'\n")
        result = drafts.finish(self.workspace, self.baseline, self.folder, agent_ok=True)
        self.assertFalse(result["draft_verified"])
        self.assertFalse(result["applied"])
        self.assertIn("syntax check failed", result["verification_failure"])
        self.assertEqual((self.services / "worker.py").read_text(), "VALUE = 'concurrent live edit'\n")
        self.assertIn("def broken", (self.folder / "proposed.diff").read_text())
        self.assertFalse((self.workspace / "conductor/keys.env").exists())

    def test_passing_checks_produce_verified_draft_never_live_apply(self):
        (self.workspace / "conductor/services/worker.py").write_text("VALUE = 'draft'\n")
        with patch.object(drafts, "run_bounded", return_value=SimpleNamespace(returncode=0)) as runner:
            result = drafts.finish(self.workspace, self.baseline, self.folder, agent_ok=True)
        self.assertTrue(result["draft_verified"])
        self.assertFalse(result["applied"])
        self.assertEqual((self.services / "worker.py").read_text(), "VALUE = 'live'\n")
        command = runner.call_args.args[0]
        self.assertEqual(command[0], "/usr/bin/sandbox-exec")
        self.assertIn("(deny network*)", command[command.index("-p") + 1])
        self.assertEqual(runner.call_args.kwargs["env"]["BOB_ROOT"], str(self.workspace))

    def test_check_failure_or_unavailable_sandbox_is_never_verified(self):
        (self.workspace / "conductor/services/worker.py").write_text("VALUE = 'draft'\n")
        with patch.object(drafts, "run_bounded", return_value=SimpleNamespace(returncode=1)):
            result = drafts.finish(self.workspace, self.baseline, self.folder, agent_ok=True)
        self.assertFalse(result["draft_verified"])
        self.assertIn("check failed", result["verification_failure"])

    def test_agent_cannot_disable_baseline_tests(self):
        (self.workspace / "conductor/services/test_services.py").write_text("raise SystemExit(0)\n")
        with patch.object(drafts, "run_bounded") as runner:
            result = drafts.finish(self.workspace, self.baseline, self.folder, agent_ok=True)
        runner.assert_not_called()
        self.assertIn("baseline test altered", result["verification_failure"])

    def test_deletions_are_in_diff_and_symlinks_are_rejected(self):
        target = self.workspace / "conductor/services/worker.py"
        target.unlink()
        changed, diff = drafts.diff(self.baseline, drafts.collect(self.workspace))
        self.assertIn("conductor/services/worker.py", changed)
        self.assertIn("+++ /dev/null", diff)
        target.symlink_to(self.services / "worker.py")
        with self.assertRaisesRegex(ValueError, "symlink"):
            drafts.collect(self.workspace)

    def test_scheduled_assessment_uses_draft_evidence_and_never_claims_application(self):
        for name in ("PROMPT.md", "BUILD-SERVICES.md"):
            (self.live / "conductor" / name).write_text("Evidence for assessment only.\n")
        def assessment(question, context, folder):
            self.assertTrue(all(Path(p).is_relative_to(folder) for p in context))
            transcript = folder / "transcript.md"
            transcript.write_text("Real recommendations would be recorded here.\n")
            return "synthesized", transcript, ["codex", "claude"]
        with patch.object(conductor_pass, "CONDUCTOR", self.live / "conductor"), \
                patch.object(conductor_pass, "ROOT", self.live), \
                patch.object(state, "CONDUCTOR", self.live / "conductor"), \
                patch.object(conductor_pass, "snapshot", return_value={}), \
                patch.object(conductor_pass, "status_report"), \
                patch.object(conductor_pass, "council_run", side_effect=assessment):
            conductor_pass.main()
        result_file, = (self.live / "conductor/passes").glob("*/result.json")
        result = json.loads(result_file.read_text())
        self.assertFalse(result["improvement_applied"])
        self.assertFalse(result["improvement_verified"])
        self.assertEqual(result["verification_failure"], "no proposed change")
        self.assertEqual((self.services / "worker.py").read_text(), "VALUE = 'live'\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)

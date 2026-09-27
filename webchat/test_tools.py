#!/usr/bin/env python3
"""Offline tests for Web Bob's allowlisted tool layer (tools.py). No live model calls."""
import json
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import tools
from app import Chat


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: Path, branch: str = "draft/test-lane") -> None:
    _git("init", "-q", "-b", branch, cwd=root)
    _git("config", "user.email", "bob@example.com", cwd=root)
    _git("config", "user.name", "Bob Test", cwd=root)
    (root / "README.md").write_text("hello\n")
    _git("add", "README.md", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_unknown_tool_is_rejected(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("delete_everything", {}, root=self.root)
        self.assertEqual(ctx.exception.code, "unknown-tool")

    def test_list_tools_matches_handlers_exactly(self):
        names = {spec["name"] for spec in tools.list_tools()}
        self.assertEqual(names, set(tools._HANDLERS))
        for spec in tools.list_tools():
            self.assertIn("description", spec)
            self.assertIn("input_schema", spec)

    def test_dispatch_logs_an_event(self):
        result = tools.dispatch("queue_add", {"description": "Do the thing"}, root=self.root)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["event_seq"], 1)
        from alignment_events import read_events
        events = read_events(self.root, since_seq=0)
        self.assertEqual(events[-1]["kind"], "tool:queue_add")
        self.assertEqual(events[-1]["tool"], "queue_add")

    def test_invalid_args_raise_tool_error_not_type_error(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("queue_add", {"unexpected_kw": 1}, root=self.root)
        self.assertEqual(ctx.exception.code, "invalid-args")


class HardBlockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_merge_is_blocked(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("queue_add", {"description": "please merge this PR"}, root=self.root)
        self.assertEqual(ctx.exception.code, "merge")

    def test_undraft_is_blocked(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("queue_add", {"description": "undraft the PR and ship it"}, root=self.root)
        self.assertEqual(ctx.exception.code, "undraft")

    def test_force_push_is_blocked(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("queue_add", {"description": "git push --force to fix it"}, root=self.root)
        self.assertEqual(ctx.exception.code, "force-push")

    def test_send_message_is_blocked(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("queue_add", {"description": "send an email to the band"}, root=self.root)
        self.assertEqual(ctx.exception.code, "send-message")

    def test_grok_worker_is_blocked(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("run_council", {"question": "ask Grok what it thinks"}, root=self.root)
        self.assertEqual(ctx.exception.code, "grok-worker")

    def test_grok_worker_is_blocked_in_lane_request(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("request_lane_start", {"lane": "grok-worker"}, root=self.root)
        self.assertEqual(ctx.exception.code, "grok-worker")

    def test_spend_is_blocked(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("queue_add", {"description": "please purchase a new plan"}, root=self.root)
        self.assertEqual(ctx.exception.code, "spend")

    def test_destructive_delete_is_blocked(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("queue_add", {"description": "just rm -rf the old worktree"}, root=self.root)
        self.assertEqual(ctx.exception.code, "destructive-delete")

    def test_unknown_tool_cannot_bypass_via_no_handler(self):
        # There is no merge/undraft/force-push/send/delete tool defined at all —
        # the regex scan is defense in depth, not the only guard.
        self.assertNotIn("merge", tools._HANDLERS)
        self.assertNotIn("git_push_force", tools._HANDLERS)
        self.assertNotIn("send_email", tools._HANDLERS)
        self.assertNotIn("delete_file", tools._HANDLERS)


class ReadFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "notes.txt").write_text("hello world sk-" + "a" * 25)
        (self.root / "keys.env").write_text("export SECRET=1")

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_file_redacts_keys(self):
        result = tools.dispatch("read_file", {"path": "notes.txt"}, root=self.root)
        self.assertNotIn("sk-" + "a" * 25, result["data"]["text"])
        self.assertIn("[secret removed]", result["data"]["text"])

    def test_read_file_blocks_credentials(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("read_file", {"path": "keys.env"}, root=self.root)
        self.assertEqual(ctx.exception.code, "blocked-secret")

    def test_read_file_blocks_path_traversal(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("read_file", {"path": "../outside.txt"}, root=self.root)
        self.assertEqual(ctx.exception.code, "outside-worktree")

    def test_read_file_missing(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("read_file", {"path": "nope.txt"}, root=self.root)
        self.assertEqual(ctx.exception.code, "not-found")


class QueueToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_queue_add_writes_ready_row(self):
        result = tools.dispatch("queue_add", {"description": "Build the thing"}, root=self.root)
        filename = result["data"]["file"]
        index = (self.root / "next-prompts/INDEX.md").read_text()
        self.assertIn(filename, index)
        self.assertIn("READY", index)

    def test_queue_prioritize_changes_priority_and_undo_restores_it(self):
        added = tools.dispatch("queue_add", {"description": "Build the thing"}, root=self.root)
        filename = added["data"]["file"]
        result = tools.dispatch("queue_prioritize", {"filename": filename, "priority": 5}, root=self.root)
        self.assertIn("| 5 |", (self.root / "next-prompts/INDEX.md").read_text())
        self.assertEqual(result["undo"]["args"]["priority"], 99)
        undone = tools.undo(result["event_seq"], root=self.root)
        self.assertIn("| 99 |", (self.root / "next-prompts/INDEX.md").read_text())
        self.assertIn("Undid event", undone["summary"])

    def test_queue_prioritize_rejects_bad_priority(self):
        added = tools.dispatch("queue_add", {"description": "Build the thing"}, root=self.root)
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("queue_prioritize", {"filename": added["data"]["file"], "priority": 0}, root=self.root)
        self.assertEqual(ctx.exception.code, "invalid-args")

    def test_queue_cancel_marks_cancelled_not_deleted(self):
        added = tools.dispatch("queue_add", {"description": "Build the thing"}, root=self.root)
        filename = added["data"]["file"]
        tools.dispatch("queue_cancel", {"filename": filename}, root=self.root)
        index = (self.root / "next-prompts/INDEX.md").read_text()
        self.assertIn(filename, index)
        self.assertIn("CANCELLED", index)

    def test_queue_cancel_missing_row(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("queue_cancel", {"filename": "nope.md"}, root=self.root)
        self.assertEqual(ctx.exception.code, "not-found")

    def test_queue_split_creates_multiple_rows(self):
        result = tools.dispatch("queue_split", {"description": "Big task", "parts": ["part a", "part b", "part c"]},
                                 root=self.root)
        self.assertEqual(len(result["data"]["files"]), 3)
        index = (self.root / "next-prompts/INDEX.md").read_text()
        for filename in result["data"]["files"]:
            self.assertIn(filename, index)

    def test_queue_split_rejects_too_few_parts(self):
        with self.assertRaises(tools.ToolError):
            tools.dispatch("queue_split", {"description": "Big task", "parts": ["only one"]}, root=self.root)


class UndoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_undo_missing_event(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.undo(999, root=self.root)
        self.assertEqual(ctx.exception.code, "not-found")

    def test_undo_when_no_undo_payload(self):
        # git_status has no undo payload.
        _init_repo(self.root)
        result = tools.dispatch("git_status", {}, root=self.root)
        with self.assertRaises(tools.ToolError) as ctx:
            tools.undo(result["event_seq"], root=self.root)
        self.assertEqual(ctx.exception.code, "no-undo")

    def test_undo_expires_after_window(self):
        added = tools.dispatch("queue_add", {"description": "Build the thing"}, root=self.root)
        from alignment_events import _folder, EVENTS_FILE
        path = _folder(self.root) / EVENTS_FILE
        lines = path.read_text().splitlines()
        rows = [json.loads(line) for line in lines]
        rows[-1]["undo_expires_at"] = time.time() - 1
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        with self.assertRaises(tools.ToolError) as ctx:
            tools.undo(added["event_seq"], root=self.root)
        self.assertEqual(ctx.exception.code, "undo-expired")


class LaneRequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lane_request_never_spawns_a_process(self):
        with patch("tools.run") as mock_run:
            result = tools.dispatch("request_lane_start", {"lane": "cursor-1", "reason": "queue is deep"},
                                     root=self.root)
        mock_run.assert_not_called()
        self.assertTrue(result["ok"])
        from alignment_events import read_events
        events = read_events(self.root, since_seq=0)
        self.assertEqual(events[-1]["kind"], "lane_start_request")

    def test_lane_stop_is_the_undo_of_start(self):
        result = tools.dispatch("request_lane_start", {"lane": "cursor-1"}, root=self.root)
        self.assertEqual(result["undo"]["tool"], "request_lane_stop")

    def test_invalid_lane_name_rejected(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("request_lane_start", {"lane": "not a valid lane!"}, root=self.root)
        self.assertEqual(ctx.exception.code, "invalid-args")


class CouncilTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_council_queues_and_excludes_grok(self):
        result = tools.dispatch("run_council", {"question": "Should we ship R14?"}, root=self.root)
        self.assertTrue(result["ok"])
        index = (self.root / "next-prompts/INDEX.md").read_text()
        self.assertIn(result["data"]["file"], index)
        job_text = (self.root / "next-prompts" / result["data"]["file"]).read_text()
        self.assertIn("no Grok", job_text)

    def test_run_council_refuses_over_cap(self):
        from billing import MINIMAX_CAP_USD
        ledger = self.root / "conductor/ledger"
        ledger.mkdir(parents=True)
        (ledger / "minimax.jsonl").write_text(
            json.dumps({"call_id": "1", "cost_usd": MINIMAX_CAP_USD + 5}) + "\n"
        )
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("run_council", {"question": "Should we ship R14?"}, root=self.root)
        self.assertEqual(ctx.exception.code, "blocked-cap")


class TestsAndDrillsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "webchat").mkdir()
        (self.root / "webchat/test_webchat.py").write_text("import sys\nsys.exit(0)\n")
        (self.root / "webchat/test_failover.py").write_text("import sys\nsys.exit(1)\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_tests_reports_pass(self):
        result = tools.dispatch("run_tests", {"target": "webchat"}, root=self.root)
        self.assertTrue(result["ok"])

    def test_run_tests_reports_failure_without_raising(self):
        result = tools.dispatch("run_tests", {"target": "failover"}, root=self.root)
        self.assertFalse(result["ok"])

    def test_run_tests_rejects_unknown_target(self):
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("run_tests", {"target": "not-a-real-suite"}, root=self.root)
        self.assertEqual(ctx.exception.code, "invalid-args")


class GitToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _init_repo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_git_branch_and_status(self):
        branch = tools.dispatch("git_branch", {}, root=self.root)
        self.assertEqual(branch["data"]["branch"], "draft/test-lane")
        status = tools.dispatch("git_status", {}, root=self.root)
        self.assertIn("draft/test-lane", status["data"]["status"])

    def test_git_diff_scoped_to_path(self):
        (self.root / "README.md").write_text("hello again\n")
        result = tools.dispatch("git_diff", {"path": "README.md"}, root=self.root)
        self.assertIn("hello again", result["data"]["diff"])

    def test_git_commit_requires_draft_branch(self):
        _git("checkout", "-q", "-b", "main", cwd=self.root)
        (self.root / "README.md").write_text("changed\n")
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("git_commit", {"message": "not allowed"}, root=self.root)
        self.assertEqual(ctx.exception.code, "not-draft-branch")

    def test_git_commit_succeeds_on_draft_branch(self):
        (self.root / "README.md").write_text("changed\n")
        result = tools.dispatch("git_commit", {"message": "update readme"}, root=self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["branch"], "draft/test-lane")
        self.assertEqual(len(result["data"]["sha"]), 40)

    def test_git_push_requires_draft_branch_and_pushes_to_origin(self):
        bare = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        _git("remote", "add", "origin", str(bare), cwd=self.root)
        result = tools.dispatch("git_push", {}, root=self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["branch"], "draft/test-lane")

    def test_git_push_never_uses_force_flag(self):
        with patch("tools.run") as mock_run:
            mock_run.side_effect = [(0, "draft/test-lane", ""), (0, "", "")]
            tools.dispatch("git_push", {}, root=self.root)
        push_argv = mock_run.call_args_list[-1].args[0]
        self.assertNotIn("--force", push_argv)
        self.assertNotIn("-f", push_argv)


class DraftPrAndCiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _init_repo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_open_draft_pr_always_passes_draft_flag(self):
        with patch("tools.run") as mock_run:
            mock_run.side_effect = [(0, "draft/test-lane", ""), (0, "https://github.com/example/repo/pull/1\n", "")]
            result = tools.dispatch("open_draft_pr", {"title": "Add tools"}, root=self.root)
        argv = mock_run.call_args_list[-1].args[0]
        self.assertIn("--draft", argv)
        self.assertNotIn("--ready", argv)
        self.assertEqual(result["data"]["url"], "https://github.com/example/repo/pull/1")

    def test_open_draft_pr_requires_draft_branch(self):
        _git("checkout", "-q", "-b", "main", cwd=self.root)
        with self.assertRaises(tools.ToolError) as ctx:
            tools.dispatch("open_draft_pr", {"title": "Add tools"}, root=self.root)
        self.assertEqual(ctx.exception.code, "not-draft-branch")

    def test_read_ci_reads_checks(self):
        with patch("tools.run") as mock_run:
            mock_run.return_value = (0, "some-check\tpass\n", "")
            result = tools.dispatch("read_ci", {}, root=self.root)
        self.assertIn("some-check", result["data"]["checks"])


class CapabilityReplyTests(unittest.TestCase):
    def test_detects_frustration_phrase(self):
        reply = tools.try_capability_reply("I need you to do more")
        self.assertIsNotNone(reply)
        self.assertIn("queue_add", reply)
        self.assertNotIn("read-only chat", reply)

    def test_detects_variants(self):
        for phrase in ("stop being read-only", "you're too limited", "just do it"):
            self.assertIsNotNone(tools.try_capability_reply(phrase))

    def test_ignores_unrelated_text(self):
        self.assertIsNone(tools.try_capability_reply("What's the weather like on the mini?"))


class FakeProviders:
    """Matches test_webchat.py's fixture: the LLM must never be reached for this reply."""

    def __init__(self):
        self.calls = []

    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}

    def reply(self, conversation, cancel, progress):
        self.calls.append(conversation)
        raise AssertionError("The LLM should never be invoked for a capability-reply message.")


class ReplayCapabilityChatTests(unittest.TestCase):
    """Replays Jeff's exact frustration line through the real chat pipeline."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "conductor/webchat"
        self.folder.mkdir(parents=True)
        self.fake = FakeProviders()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.identifier = self.chat.conversation_list()["conversations"][0]["id"]

    def tearDown(self):
        self.chat.close()
        self.tmp.cleanup()

    def test_replay_i_need_you_to_do_more(self):
        history = self.chat.submit(self.identifier, "I need you to do more", str(uuid.uuid4()))
        reply = history["messages"][-1]
        self.assertEqual(reply["status"], "done")
        self.assertNotIn("This is a read-only chat", reply["content"])
        self.assertNotIn("Bob or Jeff", reply["content"])
        for name in ("queue_add", "run_council", "git_status", "open_draft_pr"):
            self.assertIn(name, reply["content"])
        self.assertEqual(self.fake.calls, [])


if __name__ == "__main__":
    unittest.main()

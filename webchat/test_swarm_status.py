"""Saved swarm state is visible without being passed off as live worker evidence."""
import json
import time
import uuid
from unittest.mock import patch

from live_status_snapshot import build_live_status_snapshot
from ops_panel import conductor_snapshot
from reply_authority import STATUS_QUESTION, format_operational_reply
from swarm_status import read_boards
from tab_status import overview
from test_webchat import Fixture


class SwarmStatusTests(Fixture):
    def board(self, **fields):
        now = time.time()
        row = dict(worker="cursor-one", llm="cursor", vendor="openai", task="Implement path leases",
                   role="feature", branch="draft/leases", sha="a" * 40, status="running", updated_at=now,
                   lease=dict(paths=["services/leases.py"], token="private-fence"), **fields)
        board = dict(version=1, project="webbob", integration_branch="integration/webbob", updated_at=now,
                     workers={row["worker"]: row}, resolver_jobs={"resolver-one": dict(status="queued", worker_diff="private diff")})
        path = self.root / "conductor/state/projects/webbob.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(board))
        return path

    def test_snapshot_tabs_and_ops_read_same_board_without_writes_or_private_fields(self):
        path = self.board()
        before = path.read_bytes()
        with patch("ops_panel.inline_live_ops") as refresh:
            snap = build_live_status_snapshot(self.root)
            tab = overview(self.chat)
            with patch("ops_panel.subprocess.check_output", return_value="fixture\n"):
                ops = conductor_snapshot(self.root)
        refresh.assert_not_called()
        self.assertEqual(snap["project_boards"], tab["project_boards"])
        self.assertEqual(snap["project_boards"], ops["project_boards"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(snap["work_counts"]["running"], 0)
        public = snap["project_boards"]["projects"][0]
        self.assertEqual(public["workers"][0]["lease"], ["services/leases.py"])
        self.assertEqual(public["queued_resolvers"], 1)
        self.assertNotIn("private", json.dumps(public))

    def test_chat_status_answers_whos_working_on_what_from_board(self):
        self.board()
        question = "Who is working on what?"
        self.assertTrue(STATUS_QUESTION.search(question))
        self.chat.submit(self.identifier, question, str(uuid.uuid4()))
        self.wait()
        answer = self.chat.history(self.identifier)["messages"][-1]
        self.assertEqual(answer["provider"], "state")
        self.assertIn("Implement path leases", answer["content"])
        self.assertIn("cursor-one", answer["content"])
        self.assertIn("recorded running", answer["content"])
        self.assertIn("live activity is checked separately", answer["content"])
        self.assertEqual(self.fake.calls, [])

    def test_status_report_api_payload_includes_project_board(self):
        self.board()
        (self.root / "conductor/STATUS.md").write_text("Current report")
        report = self.chat.report("conductor/STATUS.md")
        self.assertEqual(report["text"], "Current report")
        self.assertEqual(report["project_boards"], read_boards(self.root))
        self.assertNotIn("private-fence", json.dumps(report))

    def test_old_assignments_are_explicitly_stale_and_diagnostics_show_branch_sha_paths(self):
        path = self.board()
        value = json.loads(path.read_text())
        value["workers"]["cursor-one"]["updated_at"] -= 1000
        value["updated_at"] -= 1000
        path.write_text(json.dumps(value))
        snap = build_live_status_snapshot(self.root)
        self.assertTrue(snap["project_boards"]["projects"][0]["stale"])
        content = format_operational_reply(snap, text="status diagnostics")
        self.assertIn("over five minutes old", content)
        self.assertIn("draft/leases @ " + "a" * 12, content)
        self.assertIn("services/leases.py", content)
        self.assertNotIn("private-fence", content)

    def test_missing_board_is_empty_and_corruption_is_visible(self):
        self.assertEqual(read_boards(self.root), dict(projects=[], errors=[]))
        self.assertFalse((self.root / "conductor/state/projects").exists())
        path = self.board()
        for data in ("{bad", "[]", '{"version":2}', '{"version":1,"project":"wrong"}'):
            path.write_text(data)
            boards = read_boards(self.root)
            self.assertEqual(boards["projects"], [])
            self.assertEqual(boards["errors"][0]["project"], "webbob")
            self.assertEqual(path.read_text(), data)

    def test_no_board_does_not_change_existing_status_text(self):
        snap = build_live_status_snapshot(self.root)
        self.assertNotIn("Project assignments", format_operational_reply(snap))

    def test_bad_worker_schema_is_reported_without_breaking_status(self):
        path = self.board()
        original = json.loads(path.read_text())
        for key, value in (("task", []), ("status", "imaginary"), ("sha", None),
                           ("updated_at", float("nan")), ("updated_at", True),
                           ("lease", dict(paths="not-a-list"))):
            board = json.loads(json.dumps(original))
            board["workers"]["cursor-one"][key] = value
            path.write_text(json.dumps(board))
            snap = build_live_status_snapshot(self.root)
            self.assertFalse(snap["project_boards"]["projects"])
            self.assertIn("project board unavailable", format_operational_reply(snap))

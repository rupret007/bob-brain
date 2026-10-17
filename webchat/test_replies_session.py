"""Exact user turns from session 8126301c; real journals, no model calls."""
import json
import uuid
from pathlib import Path
from unittest.mock import patch

from app import Chat
from chat_intent import projects
from task_dispatch import parse_work, task_queue as queue
from test_webchat import Fixture
from worker_activity import parse_processes

EXCHANGES = json.loads(Path(__file__).with_name("fixtures").joinpath("replies_session_0927.json").read_text())["exchanges"]
ASKS = [row["message"] for row in EXCHANGES]
NAMES = ["WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football"]


class SessionReplies(Fixture):
    def submit(self, text, request=None, **kwargs):
        self.chat.submit(self.identifier, text, request or str(uuid.uuid4()), **kwargs)
        self.wait()
        return self.chat.history(self.identifier)["messages"][-1]

    def evidence(self):
        screens, ps = {}, []
        for pid, screen, command, project, task in (
            (100, "lane-webjam-fix", "codex exec --model gpt-test task", "WebJam", "Fix login validation"),
            (200, "lane-adoptiq-test", "cursor-agent -p task", "AdoptIQ", "Test intake validation"),
            (300, "svc-storyboard-review", "python3 /repo/compat.py gemini -f prompt", "StoryBoard", "Review scene editing"),
            (400, "lane-fantasy-audit", "python3 /repo/compat.py minimax -f prompt", "Fantasy Football", "Audit lineup scoring"),
            (500, "lane-webjam-tests", "codex exec task", "WebJam", "Test login retries"),
        ):
            screens[screen] = f"{pid}.{screen}"
            ps.extend([f"{pid} 1 12:00 S SCREEN -dmS {screen} bash", f"{pid+1} {pid} 11:00 S {command}"])
            stem = screen.split("-", 1)[1]
            (self.root / "logs" / (stem + "-prompt-1720.txt")).write_text(f"Project: {project}\nTask: {task}. Run relevant tests.\n")
            (self.root / "logs" / (stem + "-1720.log")).write_text("Validated one case\nStill checking boundaries\n")
        board = {name: dict(state="ready") for name in ("codex", "cursor", "gemini", "minimax")}
        board["claude"] = dict(state="cooldown", detail="claude: You've hit your session limit · resets 6:20pm (America/Chicago)")
        (self.root / "conductor/lanes.json").write_text(json.dumps(board))
        return screens, parse_processes("\n".join(ps))

    def test_exact_worker_questions_criticism_and_tone_list_every_worker(self):
        (self.root / "logs").mkdir(exist_ok=True)
        screens, processes = self.evidence()
        with patch("live_status_snapshot._screen_sessions", return_value=screens), \
                patch("live_status_snapshot.process_table", return_value=processes):
            for text in ASKS[1:5] + ["What's working on what?", "what's going on each LLM"]:
                with self.subTest(text=text):
                    reply = self.submit(text)
                    answer = reply["content"]
                    self.assertEqual(reply["provider"], "state")
                    self.assertNotIn("running for", answer)
                    for task in NAMES:
                        self.assertIn(task, answer)
                    for name in NAMES:
                        self.assertIn(name, answer)
                    self.assertNotIn("running for", answer)
                    self.assertIn("Claude is cooling down until 6:20 PM CT", answer)
                    self.assertNotIn("cooling down", answer.split("Claude")[0])
                    self.assertLessEqual(len(answer.split(". ")), 4)
                    for unwanted in ("unknown task", "details unavailable", "I'll focus", "Chat health", "Recent logs", "Disk space"):
                        self.assertNotIn(unwanted.lower(), answer.lower())
        self.assertFalse(self.fake.calls)
        self.assertFalse(queue.tasks(self.root))

    def test_missing_assignment_uses_readable_lane_without_log_dump(self):
        (self.root / "logs").mkdir(exist_ok=True)
        (self.root / "logs/mystery-1720.log").write_text("phase one\nwaiting for response\n")
        with patch("live_status_snapshot._screen_sessions", return_value={"lane-mystery": "100.lane-mystery"}), \
                patch("live_status_snapshot.process_table", return_value=parse_processes(
                    "100 1 08:00 S SCREEN -dmS lane-mystery bash\n101 100 07:00 S codex exec private task")):
            answer = self.submit(ASKS[1])["content"]
        for expected in ("Codex is working on Mystery",):
            self.assertIn(expected, answer)
        for hidden in ("lane-mystery", "logs/", "waiting for response", "model not reported", "7 min"):
            self.assertNotIn(hidden, answer)
        self.assertNotIn("unknown task", answer.lower())

    def test_exact_stress_request_saves_four_scoped_draft_jobs_and_replays_once(self):
        (self.root / "conductor/lanes.json").write_text(json.dumps({
            "codex": dict(state="ready"), "cursor": dict(state="ready"), "claude": dict(state="cooldown"),
            "gemini": dict(state="ready"), "minimax": dict(state="ready")}))
        request = str(uuid.uuid4())
        receipt = self.submit(ASKS[5], request)
        self.assertEqual(receipt["provider"], "dispatcher")
        rows = [queue.tasks(self.root)[job] for job in receipt["task_ids"]]
        self.assertEqual([row["title"] for row in rows], NAMES)
        self.assertEqual({row["requested_worker"] for row in rows}, {"codex", "cursor"})
        self.assertEqual(len(receipt["content"].splitlines()), 4)
        self.assertNotIn("Started", receipt["content"])
        for row in rows:
            self.assertEqual(projects(row["prompt"]), [row["title"]])
            self.assertEqual(row["publish_project"], row["title"])
            self.assertTrue(row["draft_pr"])
            self.assertEqual(row["kind"], "coding")
            self.assertIn("worktree", row["prompt"])
            self.assertIn("draft branch", row["prompt"])
            self.assertIn(row["id"], receipt["content"])
            claim = queue.claim(self.root, row["requested_worker"], identifier=row["id"])
            self.assertIsNotNone(claim)
            queue.transition(self.root, row["id"], claim["claim_token"], "running")
            queue.transition(self.root, row["id"], claim["claim_token"], "executing")
            self.chat.reconcile_tasks()
            updated = self.chat.history(self.identifier)["messages"][1]
            self.assertEqual(updated["content"], receipt["content"])
            self.assertEqual(updated["action_card"]["state"], "running")
            queue.transition(self.root, row["id"], claim["claim_token"], "succeeded", result="Verified fixture result")
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.submit(ASKS[5], request)
        self.assertEqual(len(queue.tasks(self.root)), 4)
        self.assertFalse(self.fake.calls)

    def test_exact_initial_request_uses_saved_projects_or_asks_for_targets(self):
        answer = self.submit(ASKS[0])
        self.assertEqual(answer["content"], "Which projects should I work on?")
        self.assertFalse(queue.tasks(self.root))
        self.submit("Prioritize WebJam, AdoptIQ, StoryBoard and Fantasy Football")
        answer = self.submit(ASKS[0])
        self.assertEqual([queue.tasks(self.root)[job]["title"] for job in answer["task_ids"]], NAMES)
        self.assertFalse(self.fake.calls)

    def test_action_does_not_turn_into_status_and_questions_or_negation_do_not_dispatch(self):
        for text in ("Should we start WebJam and AdoptIQ?", "Don't start WebJam and AdoptIQ", "What would happen if we start all projects?"):
            self.assertEqual(parse_work(text), (None, "auto"))
        self.assertTrue(parse_work(ASKS[5])[0])
        self.assertTrue(parse_work("push WebJam and Stkryboard")[0])
        self.assertEqual(projects("WebJam, AdoptiQ, Stkryboard, Storyboard, Fantasy Football"), NAMES)

    def test_status_stays_authoritative_for_every_explicit_chat_provider(self):
        for provider in ("codex", "claude", "cursor", "gemini", "minimax"):
            reply = self.submit(ASKS[4], provider=provider)
            self.assertEqual(reply["provider"], "state")
            self.assertIn("Codex", reply["content"])
            self.assertIn("are idle", reply["content"])
        self.assertFalse(self.fake.calls)

"""Regression tests for the WEBBOB-REPLYQ-1856 reply-quality pass.

Each Jeff message here is taken verbatim from his real webchat sessions
(conductor/webchat/sessions/8126301c-... and .../65a5d782-...). These pin down
the concrete failures he hit — empty promises, "unknown task", raw log dumps,
a robotic "Yes —" prefix on non yes/no questions, and status queries that
never actually named a worker/task — so they cannot silently come back.
"""
import tempfile
import json
import re
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app import Chat
from providers import RULES
from reply_authority import format_operational_reply
from test_worker_activity import PS, SCREENS
from worker_activity import parse_processes
from worker_evidence import clean, _log_model
from task_dispatch import task_queue


class FakeProviders:
    """Stands in for the real LLM CLIs; only used for the free-text (non-status) turns."""

    def __init__(self, reply_text="Hi Jeff!"):
        self.calls = []
        self.reply_text = reply_text

    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}

    def reply(self, conversation, cancel, progress):
        self.calls.append(conversation)
        progress("gemini", [])
        return {"content": self.reply_text, "provider": "gemini", "codex_thread_id": None, "attempts": []}


class SessionFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "conductor/webchat"
        self.folder.mkdir(parents=True)
        self.fake = FakeProviders()
        self.chat = Chat(self.folder, self.root, self.fake)
        self.identifier = self.chat.conversation_list()["conversations"][0]["id"]
        for name in ("_screen_sessions", "process_table"):
            sampler = patch("live_status_snapshot." + name, return_value={})
            sampler.start()
            self.addCleanup(sampler.stop)

    def tearDown(self):
        self.chat.close()
        self.tmp.cleanup()

    def send(self, text):
        request_id = str(uuid.uuid4())
        self.chat.submit(self.identifier, text, request_id)
        info = self.chat.workers.get(self.identifier)
        if info:
            info["thread"].join(3)
        return self.chat.get(self.identifier)["messages"][-1]


class Session8126301cTests(SessionFixture):
    """'Ok start up all the projects we were working on taking everything' (2026-09-27)."""

    def test_start_all_projects_without_names_asks_which_projects_not_an_empty_promise(self):
        reply = self.send("Ok start up all the projects we were working on taking everything to the max.")
        self.assertEqual(reply["content"], "Which projects should I work on?")
        self.assertNotIn("I'll focus", reply["content"])

    def test_whats_working_on_what_never_says_unknown_task(self):
        reply = self.send("Ok what’s working on what?")
        self.assertEqual(reply["provider"], "state")
        self.assertNotIn("unknown", reply["content"].lower())
        self.assertIn("Codex", reply["content"])

    def test_cant_have_unknown_tasks_reply_itself_has_no_unknown_task(self):
        reply = self.send("Ok we can’t have unknown tasks. We need to also know what’s going on what resources.")
        self.assertEqual(reply["provider"], "state")
        self.assertNotIn("unknown task", reply["content"].lower())

    def test_this_needs_to_be_way_better_gives_a_fresh_answer_not_a_promise(self):
        self.send("Ok we can’t have unknown tasks. We need to also know what’s going on what resources.")
        reply = self.send("This needs to be way better")
        self.assertNotIn("I'll focus", reply["content"])
        self.assertNotIn("I understand", reply["content"])
        self.assertNotIn("I'll do better", reply["content"])

    def test_whats_going_on_each_llm_names_workers(self):
        reply = self.send("What’s going on each LLM")
        self.assertEqual(reply["provider"], "state")
        self.assertIn("Codex", reply["content"])
        self.assertIn("Claude", reply["content"])

    def test_four_named_projects_actually_dispatches_instead_of_a_status_dump(self):
        reply = self.send(
            "Ok we want it to start up at max all the projects we were working on before. Remember. "
            "WebJam, AdoptIQ, Stkryboard, Fantasy Football. All of these need to be developed to the max "
            "using and and all resources. This is a stress test essentially."
        )
        self.assertEqual(reply["provider"], "dispatcher")
        for project in ("WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football"):
            self.assertIn(project, reply["content"])
        self.assertNotIn("Which projects", reply["content"])

    def test_hi_gets_a_short_greeting(self):
        self.fake.reply_text = "Hi Jeff!"
        reply = self.send("Hi")
        self.assertEqual(reply["content"], "Hi Jeff!")

    def test_status_of_everything_names_worker_and_task_with_no_yes_prefix_or_unknown(self):
        with patch("live_status_snapshot._screen_sessions", return_value=SCREENS), \
                patch("live_status_snapshot.process_table", return_value=parse_processes(PS)):
            reply = self.send("What’s the status or everything.")
        self.assertEqual(reply["provider"], "state")
        self.assertIn("Codex", reply["content"])
        self.assertIn("Claude", reply["content"])
        self.assertNotIn("Yes —", reply["content"])
        self.assertNotIn("unknown", reply["content"].lower())

    def test_hows_it_going_does_not_answer_yes_to_a_non_yes_no_question(self):
        with patch("live_status_snapshot._screen_sessions", return_value=SCREENS), \
                patch("live_status_snapshot.process_table", return_value=parse_processes(PS)):
            reply = self.send("How’s it going?")
        self.assertEqual(reply["provider"], "state")
        self.assertFalse(reply["content"].startswith("Yes"))
        self.assertIn("working on", reply["content"])
        self.assertNotIn("running for", reply["content"])


class Session65a5d782Tests(SessionFixture):
    """'push WebJam and AdoptIQ' (2026-09-27)."""

    def test_push_webjam_and_adoptiq_dispatches_both_named_projects(self):
        reply = self.send("push WebJam and AdoptIQ")
        self.assertEqual(reply["provider"], "dispatcher")
        self.assertIn("WebJam", reply["content"])
        self.assertIn("AdoptIQ", reply["content"])

    def test_receipt_stays_truthful_after_completion_and_reload(self):
        receipt = self.send("push WebJam and AdoptIQ")
        original = receipt["content"]
        created = receipt["created_at"]
        for identifier in receipt["task_ids"]:
            row = task_queue.tasks(self.root)[identifier]
            self.assertIn(identifier, original)
            claim = task_queue.claim(self.root, row["requested_worker"], identifier=identifier)
            task_queue.transition(self.root, identifier, claim["claim_token"], "running")
            task_queue.transition(self.root, identifier, claim["claim_token"], "succeeded", result="Verified fixture change")
        self.chat.reconcile_tasks()
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        messages = self.chat.get(self.identifier)["messages"]
        saved = next(m for m in messages if m["id"] == receipt["id"])
        self.assertEqual((saved["content"], saved["created_at"]), (original, created))
        self.assertNotIn("Finished", saved["content"])
        self.assertEqual(saved["action_card"]["state"], "done")
        results = [m for m in messages if m.get("task_status") == "succeeded"]
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0]["created_at"], created)


class SystemPromptStyleRubricTests(unittest.TestCase):
    """Static checks on the RULES persona text itself (providers.py)."""

    def test_never_instructs_the_model_to_call_a_task_unknown(self):
        lowered = RULES.lower()
        self.assertNotIn("must stay unknown", lowered)
        self.assertNotIn("say its current task is unknown", lowered)
        self.assertIn('never say "unknown task"', lowered)

    def test_explicitly_bans_empty_improvement_promises(self):
        lowered = RULES.lower()
        self.assertIn("i'll focus on...", lowered)
        self.assertIn("give the corrected, better answer right now", lowered)

    def test_requires_casual_answer_first_short_style(self):
        self.assertIn("1 to 4 short, casual", RULES)

    def test_warns_against_mixing_up_per_provider_limits(self):
        lowered = RULES.lower()
        self.assertIn("never state one provider's cap or reset time as if it were another's", lowered)


class OperationalReplyFormattingTests(unittest.TestCase):
    """Direct unit coverage for the deterministic status formatter (reply_authority)."""

    def _snapshot(self, running=1):
        return {
            "queue_counts": {"claimed": 0, "queued": 0},
            "work": [dict(worker="codex", model="gpt-fixture", task="Review Web Bob replies", state="running", elapsed_seconds=60) for _ in range(running)],
            "inspection": {"screens": True, "processes": True},
            "work_counts": {"running": running},
            "screen_lanes": [],
            "disk": {},
            "lane_locks": {},
            "provider_health": {},
        }

    def test_running_workers_line_has_no_yes_prefix(self):
        text = format_operational_reply(self._snapshot(running=2), "server", "how's it going?")
        self.assertTrue(text.startswith("Codex is working on Review Web Bob replies"))
        self.assertNotIn("running for", text)
        self.assertNotIn("Yes", text)

    def test_single_running_worker_uses_singular_verb_with_no_yes_prefix(self):
        text = format_operational_reply(self._snapshot(running=1), "server", "how's it going?")
        self.assertTrue(text.startswith("Codex is working on Review Web Bob replies"))
        self.assertNotIn("running for", text)

    def test_fallback_task_has_no_log_dump_and_diagnostics_are_opt_in(self):
        snap = self._snapshot()
        snap["work"][0].update(task=None, title="Web Bob replies", screen="lane-webbob-replies", pid=8912,
                               log_path="logs/replies.log", last_log_line="Raw output " * 100)
        casual = format_operational_reply(snap, text="How's it going?")
        self.assertIn("Web Bob replies", casual)
        self.assertNotIn("gpt-fixture", casual)
        for value in ("logs/", "lane-", "8912", "Raw output", " | "):
            self.assertNotIn(value, casual)
        self.assertLessEqual(len(re.split(r"[.!?]\s+", casual)), 4)
        diagnostic = format_operational_reply(snap, text="Status with diagnostics")
        self.assertIn("logs/replies.log", diagnostic)
        self.assertIn("8912", diagnostic)

    def test_busy_lane_and_unreadable_queue_do_not_become_idle_or_empty(self):
        snap = self._snapshot(0)
        snap["inspection"]["queue_available"] = False
        snap["lane_locks"]["claude"] = dict(state="busy")
        reply = format_operational_reply(snap, text="What's working on what?")
        self.assertIn("Claude has activity I can't confirm yet", reply)
        self.assertIn("A live check failed", reply)
        self.assertNotIn("idle", reply)
        self.assertNotIn("0 queued", reply)


class ModelEvidenceTests(unittest.TestCase):
    def test_model_comes_from_current_cli_startup_not_log_prose(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "worker.log"
            row = dict(worker="codex", elapsed_seconds=30)
            metadata = type("Stat", (), {"st_birthtime": time.time()})()
            with patch.object(Path, "stat", return_value=metadata), \
                    patch.object(Path, "is_file", return_value=True), \
                    patch.object(Path, "is_symlink", return_value=False), \
                    patch("worker_evidence.read_part", return_value="OpenAI Codex v1\nmodel: gpt-observed\nuser\nmodel: invented"):
                self.assertEqual(_log_model(path, row), "gpt-observed")
                metadata.st_birthtime -= 3600
                self.assertIsNone(_log_model(path, row))
            path.write_text("Task: review a model\nmodel: invented\n")
            self.assertIsNone(_log_model(path, row))


class LogExcerptTruncationTests(unittest.TestCase):
    """worker_evidence.clean() must never hand back a word chopped in half."""

    def test_long_line_truncates_on_a_word_boundary(self):
        line = "Colloquial \"text ...\" now reaches the model so Web Bob can make good on texting requests today"
        normalized = " ".join(line.split())
        result = clean(line, 60)
        self.assertLessEqual(len(result), 60)
        self.assertTrue(normalized.startswith(result))
        # A boundary cut lands exactly on a space (or the whole string); never mid-word.
        self.assertTrue(len(result) == len(normalized) or normalized[len(result)] == " ")

    def test_short_line_is_unchanged(self):
        self.assertEqual(clean("waiting for response"), "waiting for response")

    def test_exact_word_boundary_and_unbroken_tokens(self):
        self.assertEqual(clean("full word next", 9), "full word")
        self.assertEqual(clean("unbrokenidentifier", 8), "")


if __name__ == "__main__":
    unittest.main()

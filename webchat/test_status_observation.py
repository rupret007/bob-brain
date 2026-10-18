"""Durable render-time evidence through startup races, retries and restarts."""
import copy
import json
import stat
import time
import uuid
from unittest.mock import patch

from app import Chat
from integration_rubric import check_reply
from live_status_snapshot import build_live_status_snapshot
from reply_authority import format_operational_reply
from status_observation import observation_errors, snapshot_digest
from task_dispatch import task_queue as queue
from test_webbob_replyq_1856 import SessionFixture
from worker_activity import parse_processes


QUESTION = "Ok great works on all LLMs now?"


class StatusObservationTests(SessionFixture):
    def status(self, question=QUESTION):
        before = build_live_status_snapshot(self.root)
        started = time.time()
        answer = self.send(question)
        after = build_live_status_snapshot(self.root)
        return answer, started, before, after

    def errors(self, answer, started, before, after, question=QUESTION):
        return check_reply(answer, dict(message=question, expected="status"), self.identifier,
                           started, before, after, queue.tasks(self.root))

    def job(self, index=0, worker="gemini"):
        return queue.enqueue(self.root, "external", str(uuid.uuid4()), "Review Web Bob task " + str(index),
                             worker=worker, kind="audit" if worker in ("gemini", "minimax") else "coding",
                             title="Web Bob task " + str(index))

    def claim(self, row, pid):
        claimed = queue.claim(self.root, row["requested_worker"], identifier=row["id"])
        return queue.transition(self.root, row["id"], claimed["claim_token"], "running", pid=pid)

    def processes(self, rows):
        return parse_processes("\n".join(
            f"{row['pid']} 1 00:01 S python3 /fixture/services/dispatch_worker.py {row['id']} private-claim-token"
            for row in rows))

    def test_startup_1_to_3_to_5_uses_exact_saved_sample_not_endpoints(self):
        rows = [self.claim(self.job(i, worker), 100 + i)
                for i, worker in enumerate(("codex", "gemini", "minimax", "gemini", "minimax"))]
        with patch("live_status_snapshot.process_table", side_effect=[self.processes(rows[:1]),
                self.processes(rows[:3]), self.processes(rows)]) as sampler:
            answer, started, before, after = self.status()
        observed = answer["status_observation"]["snapshot"]
        self.assertEqual([snap["work_counts"]["running"] for snap in (before, observed, after)], [1, 3, 5])
        self.assertEqual(observed["work_counts"]["claimed"], 2)
        self.assertIn("Codex", answer["content"])
        self.assertIn("Gemini", answer["content"])
        self.assertIn("MiniMax", answer["content"])
        self.assertNotIn("running for", answer["content"])
        self.assertEqual(sampler.call_count, 3)
        self.assertEqual(self.errors(answer, started, before, after), [])
        self.assertNotIn("private-claim-token", json.dumps(answer))
        # Matching a later count is still dishonest about this reply's sample.
        forged = copy.deepcopy(answer)
        forged["content"] = format_operational_reply(after)
        forged["status_observation"]["snapshot"] = after
        self.assertTrue(self.errors(forged, started, before, after))

    def test_queued_claimed_reused_pid_and_running_observations_remain_distinct(self):
        row = self.job()
        waiting, started, before, after = self.status()
        self.assertIn("waiting to run", waiting["content"])
        self.assertFalse(self.errors(waiting, started, before, after))
        row = self.claim(row, 101)
        wrong_process = parse_processes("101 1 00:01 S python3 dispatch_worker.py another-job token")
        for processes, state in (({}, "claimed"), (wrong_process, "claimed"), (self.processes([row]), "running")):
            with self.subTest(state=state, processes=processes), patch("live_status_snapshot.process_table", return_value=processes):
                answer, started, before, after = self.status()
            observed = answer["status_observation"]["snapshot"]
            self.assertEqual(observed["work_counts"][state], 1)
            self.assertFalse(self.errors(answer, started, before, after))
        self.assertIn("waiting to run", self.chat.history(self.identifier)["messages"][1]["content"])

    def test_snapshot_is_atomic_private_and_immutable_across_retry_and_restart(self):
        answer, started, before, after = self.status()
        original = copy.deepcopy(answer)
        path = self.chat.state / (self.identifier + ".json")
        self.assertEqual(json.loads(path.read_text())["messages"][-1], original)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        public = self.chat.history(self.identifier)
        public["messages"][-1]["status_observation"]["snapshot"]["work"].append({"fake": True})
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        with patch("reply_authority.build_live_status_snapshot", side_effect=AssertionError("Must not recapture")):
            retried = self.chat.submit(self.identifier, QUESTION, original["request_id"])["messages"][-1]
            self.assertEqual(retried, original)
            self.assertEqual(self.chat.history(self.identifier)["messages"][-1], original)
        self.assertFalse(self.errors(retried, started, before, after))

    def test_status_rendering_identity_is_atomic_with_saved_evidence(self):
        from reply_delivery import rendering
        answer, started, before, after = self.status()
        path = self.chat.state / (self.identifier + ".json")
        saved = json.loads(path.read_text())["messages"][-1]
        expected = rendering(saved)[0]
        self.assertEqual(saved.get("reply_delivery"), expected)
        self.assertEqual(answer["reply_delivery"], expected)
        self.assertEqual(saved["status_observation"], answer["status_observation"])
        original = path.read_bytes()
        self.chat.history(self.identifier)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse((self.chat.state / "reply-receipts.sqlite").exists())
        self.assertFalse(self.errors(answer, started, before, after))
        # Identity alone never acknowledges delivery or executes any action.
        self.assertFalse(self.chat.workers)

    def test_write_failure_cannot_expose_a_successful_unpersisted_status(self):
        from app import private_write
        def fail_completed(path, value):
            if '"status_observation"' in value:
                raise OSError("fixture disk failure")
            private_write(path, value)
        with patch("app.private_write", side_effect=fail_completed), self.assertRaises(OSError):
            self.send(QUESTION)
        saved = json.loads((self.chat.state / (self.identifier + ".json")).read_text())["messages"][-1]
        self.assertNotEqual(saved["status"], "done")
        self.assertNotEqual(self.chat.get(self.identifier)["messages"][-1]["status"], "done")

    def test_correction_has_its_own_bound_observation(self):
        first = self.send(QUESTION)
        answer, started, before, after = self.status("This needs to be way better")
        self.assertNotEqual(first["status_observation"]["message_id"], answer["status_observation"]["message_id"])
        self.assertFalse(self.errors(answer, started, before, after, "This needs to be way better"))

    def test_provider_fallback_status_is_observed_and_bound_to_the_overlay(self):
        overlay = self.root / "overlay"
        overlay.mkdir()
        self.chat.overlay_roots[self.identifier] = overlay
        queue.enqueue(overlay, "fixture", "request", "Review overlay task", worker="gemini", kind="audit", title="Overlay task")
        started = time.time()
        self.chat.submit(self.identifier, QUESTION, str(uuid.uuid4()), provider="gemini")
        info = self.chat.workers.get(self.identifier)
        if info:
            info["thread"].join(3)
        answer = self.chat.history(self.identifier)["messages"][-1]
        self.assertEqual(answer["status"], "done")
        self.assertTrue(self.fake.calls)
        self.assertIn("Overlay task", json.dumps(answer["status_observation"]["snapshot"]))
        self.assertIn("Gemini has work waiting to run", answer["content"])
        self.assertFalse(observation_errors(answer, QUESTION, self.identifier, started, time.time()))

    def test_provider_metadata_cannot_forge_an_observation(self):
        forged = dict(content="Hi Jeff!", provider="gemini", attempts=[], status_observation={"fake": True})
        with patch.object(self.fake, "reply", return_value=forged):
            answer = self.send("Hi")
        self.assertNotIn("status_observation", answer)

    def test_snapshot_and_reply_are_redacted_before_hashing_and_persistence(self):
        marker = self.chat.password  # Synthetic credential from the isolated Chat fixture.
        queue.enqueue(self.root, "external", "fixture", "Review " + marker, worker="gemini", kind="audit", title="Review " + marker)
        answer, started, before, after = self.status()
        self.assertNotIn(marker, json.dumps(answer))
        self.assertIn("[secret removed]", json.dumps(answer["status_observation"]["snapshot"]))
        self.assertNotIn(marker, (self.chat.state / (self.identifier + ".json")).read_text())
        self.assertFalse(self.errors(answer, started, before, after))

    def test_missing_stale_foreign_malformed_and_modified_evidence_fail_closed(self):
        answer, started, before, after = self.status()
        mutations = {
            "missing": lambda a, o: a.pop("status_observation"),
            "version": lambda a, o: o.update(schema_version=2),
            "foreign conversation": lambda a, o: o.update(conversation_id="other"),
            "foreign request": lambda a, o: o.update(request_id="other"),
            "foreign message": lambda a, o: o.update(message_id="other"),
            "question": lambda a, o: o.update(question="another question"),
            "stale": lambda a, o: o.update(observed_from=started - 30),
            "future": lambda a, o: o.update(observed_until=time.time() + 30),
            "not finite": lambda a, o: o.update(observed_from=float("nan")),
            "naive timestamp": lambda a, o: o["snapshot"].update(captured_at="2026-09-27T00:00:00"),
            "digest": lambda a, o: o.update(snapshot_sha256="0" * 64),
            "altered snapshot": lambda a, o: o["snapshot"]["work_counts"].update(running=10),
            "altered reply": lambda a, o: a.update(content=a["content"].replace("idle", "running")),
            "malformed": lambda a, o: o.update(snapshot=[]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                modified = copy.deepcopy(answer)
                mutate(modified, modified["status_observation"])
                self.assertTrue(self.errors(modified, started, before, after))

    def test_digest_and_matching_prose_cannot_replace_observed_worker_evidence(self):
        row = self.claim(self.job(), 101)
        with patch("live_status_snapshot.process_table", return_value=self.processes([row])):
            answer, started, before, after = self.status()
        mutations = {
            "missing pid": lambda s: s["work"][0].update(pid=None),
            "queue source": lambda s: s["work"][0].update(source="queue"),
            "no assignment": lambda s: s["work"][0].update(assignment_recorded=False),
            "failed inspection": lambda s: s["inspection"].update(processes_available=False),
            "worker count": lambda s: s["work_counts"].update(running=2),
            "queue count": lambda s: s["queue_counts"].update(claimed=2),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                modified = copy.deepcopy(answer)
                snap = modified["status_observation"]["snapshot"]
                mutate(snap)
                modified["status_observation"]["snapshot_sha256"] = snapshot_digest(snap)
                modified["content"] = format_operational_reply(snap)
                self.assertTrue(self.errors(modified, started, before, after))

    def test_legacy_history_loads_without_inventing_a_snapshot(self):
        answer = self.send(QUESTION)
        self.chat.get(self.identifier)["messages"][-1].pop("status_observation")
        self.chat.save(self.chat.get(self.identifier))
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        restored = self.chat.history(self.identifier)["messages"][-1]
        self.assertEqual(restored["content"], answer["content"])
        self.assertNotIn("status_observation", restored)
        self.assertTrue(observation_errors(restored, QUESTION, self.identifier, 0, time.time()))

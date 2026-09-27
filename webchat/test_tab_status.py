"""Current tab data must not borrow values from stale dashboards or lane caches."""
import http.client
import json
import os
import threading
import time
from unittest.mock import patch

import test_webchat
from app import Server
from tab_status import overview, recorded_usage
from worker_activity import parse_processes


class TabStatusTests(test_webchat.Fixture):
    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return path

    def test_overview_is_read_only_and_excludes_old_dashboard_rows(self):
        self.write("conductor/dashboard.json", json.dumps(dict(live_ops=dict(
            generated_at="2020-01-01T00:00:00+00:00", now_line="old drill",
            scores=[dict(area="UX", score="10/10")], running_jobs=[dict(job_id="fake")]))))
        self.write("conductor/lanes.json", json.dumps(dict(minimax=dict(budget=dict(committed_usd=99)))))
        self.write("conductor/state/queue.jsonl", "\n".join(json.dumps(dict(
            id=f"job-{i}", status="queued", title=f"Task {i}", updated_at=i)) for i in range(28)))
        before = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        with patch("ops_panel.inline_live_ops") as refresh:
            data = overview(self.chat)
        refresh.assert_not_called()
        self.assertEqual(len(data["queued"]), 28)
        self.assertEqual(data["work"], [])
        self.assertNotIn("scores", data)
        self.assertNotIn("fake", json.dumps(data))
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()})

    def test_live_worker_and_queue_claim_are_one_job(self):
        self.write("conductor/state/queue.jsonl", json.dumps(dict(
            id="job-one", status="running", pid=100, worker="codex", title="Review login")))
        processes = parse_processes("100 1 01:00 S codex exec --model test-model task\n101 100 00:59 S codex exec task")
        with patch("live_status_snapshot.process_table", return_value=processes):
            data = overview(self.chat)
        self.assertEqual(len(data["work"]), 1)
        self.assertEqual(data["work"][0]["title"], "Review login")
        self.assertEqual(data["work"][0]["elapsed_seconds"], 60)
        self.assertEqual(data["work"][0]["state"], "running")
        self.assertEqual(data["queued"], [])

    def test_unavailable_inspection_and_damaged_queue_are_not_empty_success(self):
        self.write("conductor/state/queue.jsonl", '{"id":')
        with patch("live_status_snapshot.process_table", return_value=None), \
                patch("live_status_snapshot._screen_sessions", return_value=None):
            data = overview(self.chat)
        self.assertEqual(data["inspection"], dict(processes_available=False, screens_available=False, queue_available=False))

    def test_usage_reads_current_ledger_and_does_not_invent_zero_or_cap(self):
        self.write("conductor/lanes.json", json.dumps(dict(minimax=dict(budget=dict(committed_usd=99, cap_usd=59)))))
        self.assertEqual(recorded_usage(self.root, "minimax", now=time.time()), {})
        path = self.write("conductor/ledger/minimax.jsonl", "\n".join(json.dumps(row) for row in [
            dict(call_id="one", reserved_usd=4), dict(call_id="one", cost_usd=1.25),
            dict(call_id="two", reserved_usd=.5)]))
        result = recorded_usage(self.root, "minimax", now=time.time())
        self.assertEqual(result["spent_usd"], 1.25)
        self.assertEqual(result["reserved_usd"], .5)
        self.assertNotIn("cap_usd", result)
        path.write_text(path.read_text() + '\n{"call_id":')
        self.assertEqual(recorded_usage(self.root, "minimax", now=time.time()), {})
        for value in (None, False, -1, float("nan")):
            path.write_text(json.dumps(dict(call_id="unknown", cost_usd=value)))
            self.assertEqual(recorded_usage(self.root, "minimax", now=time.time()), {})

    def test_expired_stale_or_invalid_plan_measurements_are_hidden(self):
        now = time.time()
        path = self.write("conductor/plan-usage.json", json.dumps(dict(codex=dict(used_percent=0, reset_at=now + 3600))))
        os.utime(path, (now, now))
        self.assertEqual(recorded_usage(self.root, "codex", now=now)["used_percent"], 0)
        os.utime(path, (now - 86401, now - 86401))
        self.assertEqual(recorded_usage(self.root, "codex", now=now), {})
        for percent, reset in [(50, now - 1), (float("nan"), now + 100), (101, now + 100)]:
            path.write_text(json.dumps(dict(codex=dict(used_percent=percent, reset_at=reset))))
            self.assertEqual(recorded_usage(self.root, "codex", now=now), {})

    def test_model_failure_without_work_has_no_invented_model_rows(self):
        with patch.object(self.fake, "health", side_effect=OSError("unavailable")):
            data = overview(self.chat)
        self.assertEqual(data["models"], {})
        self.assertTrue(data["inspection"]["processes_available"])

    def test_model_failure_keeps_observed_activity_and_plain_task_labels(self):
        processes = parse_processes("100 1 01:00 S codex exec task")
        self.write("conductor/state/queue.jsonl", json.dumps(dict(
            id="job-one", status="running", pid=100, worker="codex", title="Review login · abc1234")))
        with patch.object(self.fake, "health", side_effect=OSError("unavailable")), \
                patch("live_status_snapshot.process_table", return_value=processes):
            data = overview(self.chat)
        self.assertEqual(list(data["models"]), ["codex"])
        self.assertIsNone(data["models"]["codex"]["state"])
        self.assertEqual(data["work"][0]["title"], "Review login")
        self.assertEqual(data["work"][0]["state"], "running")

    def test_overview_requires_login_and_redacts_private_values(self):
        self.write("conductor/state/queue.jsonl", json.dumps(dict(
            id="private-task", status="queued", title=self.chat.password)))
        server = Server(("127.0.0.1", 0), self.chat)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection(*server.server_address, timeout=10)
        try:
            connection.request("GET", "/api/overview")
            response = connection.getresponse()
            self.assertEqual(response.status, 401)
            response.read()
            connection.request("POST", "/login", "password=" + self.chat.password,
                               {"Content-Type": "application/x-www-form-urlencoded"})
            response = connection.getresponse()
            cookie = response.getheader("Set-Cookie").split(";", 1)[0]
            response.read()
            connection.request("GET", "/api/overview", headers={"Cookie": cookie})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            body = response.read().decode()
            self.assertNotIn(self.chat.password, body)
            self.assertEqual(json.loads(body)["queued"][0]["job_id"], "private-task")
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            thread.join(2)

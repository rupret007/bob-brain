"""Process evidence regressions; no worker/model is launched."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from worker_activity import collect_work, elapsed_seconds, parse_processes, process_table


SCREENS = {"lane-projects-push": "100.lane-projects-push", "lane-webbob-clean": "200.lane-webbob-clean",
           "lane-webbob-clean2": "300.lane-webbob-clean2", "lane-webbob-minimax": "400.lane-webbob-minimax",
           "svc-job-runner": "500.svc-job-runner"}
PS = """
100 1 40:00 Ss SCREEN -dmS lane-projects-push /tmp/project-push.sh
101 100 40:00 Ss+ login -pflq jeff /tmp/project-push.sh
102 101 39:59 S+ /bin/bash /tmp/project-push.sh
103 102 24:00 S+ /opt/homebrew/bin/claude --model opus -p Private task text
200 1 30:00 Ss SCREEN -dmS lane-webbob-clean bash
201 200 29:59 S+ /bin/bash
202 201 18:00 S+ node /opt/node_modules/@openai/codex/bin/codex.js exec --model gpt-fixture Private prompt
203 202 17:59 S+ /opt/codex/vendor/aarch64/codex exec --model gpt-fixture Private prompt
300 1 20:00 Ss SCREEN -dmS lane-webbob-clean2 bash
301 300 20:00 S+ /bin/bash
302 301 12:00 R+ codex exec --dangerously-bypass-approvals-and-sandbox Follow-up 2: Jeff's task --model not-a-real-model
400 1 15:00 Ss SCREEN -dmS lane-webbob-minimax bash
401 400 15:00 S+ /bin/bash
402 401 08:00 S+ codex exec Fix MiniMax
500 1 2-02:00:00 Ss SCREEN -dmS svc-job-runner bash
501 500 2-02:00:00 S+ python3 runtime.py job-runner
"""


class WorkerActivityTests(unittest.TestCase):
    def test_empty_queue_includes_four_screen_workers_and_actual_models(self):
        work = collect_work(SCREENS, [], parse_processes(PS), 10000)
        self.assertEqual(len(work), 4)
        by_screen = {row["screen"]: row for row in work}
        self.assertEqual(by_screen["lane-projects-push"]["worker"], "claude")
        self.assertEqual(by_screen["lane-projects-push"]["model"], "opus")
        self.assertEqual(by_screen["lane-projects-push"]["elapsed_seconds"], 24 * 60)
        for screen in SCREENS:
            if screen.startswith("lane-webbob"):
                self.assertEqual(by_screen[screen]["worker"], "codex")
                self.assertEqual(by_screen[screen]["state"], "running")
        self.assertEqual(by_screen["lane-webbob-clean"]["model"], "gpt-fixture")
        self.assertIsNone(by_screen["lane-webbob-clean2"]["model"])
        self.assertNotIn("Private", json.dumps(work))
        self.assertNotIn("command", json.dumps(work))

    def test_claim_screen_wrapper_and_worker_count_once(self):
        record = dict(job_id="private-job-id", worker="codex", pid=201, title="Fix chat status", started_at=9000)
        work = collect_work(SCREENS, [record], parse_processes(PS), 10000)
        self.assertEqual(len(work), 4)
        match = next(row for row in work if row.get("job_id"))
        self.assertEqual(match["job_id"], "private-job-id")
        self.assertEqual(match["title"], "Fix chat status")
        self.assertEqual(match["state"], "running")

    def test_standalone_workers_count_but_desktop_helpers_and_mentions_do_not(self):
        processes = parse_processes("""
10 1 04:00 S codex exec --model=gpt-fixture Work
20 1 02:00 S /home/test/.local/bin/cursor-agent --use-system-ca /home/test/.local/share/cursor-agent/versions/example/index.js -p Work
30 1 01:00 S python3 tests.py codex exec example
40 1 01:00 S bash -c codex exec old command
50 1 3-01:00:00 S /Applications/Claude.app/Contents/MacOS/Claude
60 1 3-01:00:00 S /Applications/ChatGPT.app/Contents/Frameworks/Codex Framework.framework/Helpers/browser_crashpad_handler
70 1 3-01:00:00 S /Applications/ChatGPT.app/Contents/Resources/codex -c features.code_mode_host=true app-server
80 1 3-01:00:00 S /home/test/.codex/computer-use/Codex Computer Use.app/Contents/MacOS/Helper
""")
        work = collect_work({}, [], processes, 10000)
        self.assertEqual([row["worker"] for row in work], ["codex", "cursor"])
        self.assertEqual(work[0]["model"], "gpt-fixture")
        self.assertEqual(work[0]["title"], "Worker process")

    def test_open_screens_stopped_workers_and_zombies_do_not_claim_progress(self):
        processes = parse_processes(PS.replace("24:00 S+", "24:00 T+").replace("08:00 S+", "08:00 Z+"))
        work = collect_work(SCREENS, [], processes, 10000)
        by_screen = {row["screen"]: row for row in work}
        self.assertEqual(by_screen["lane-projects-push"]["state"], "paused")
        self.assertEqual(by_screen["lane-webbob-minimax"]["state"], "unverified")
        self.assertIsNone(by_screen["lane-webbob-minimax"]["worker"])
        disappeared = collect_work(SCREENS, [], {}, 10000)
        self.assertEqual(len(disappeared), 4)
        self.assertTrue(all(row["state"] == "unverified" for row in disappeared))

    def test_failed_process_check_keeps_claim_and_screen_uncertainty(self):
        work = collect_work(SCREENS, [dict(job_id="job", worker="claude", claimed_at=9000)], None, 10000)
        self.assertEqual(work[0]["state"], "claimed")
        self.assertEqual(work[0]["elapsed_seconds"], 1000)
        self.assertTrue(all(row["state"] == "unverified" for row in work[1:]))

    def test_api_dispatch_process_is_live_but_reused_pid_is_not(self):
        record = dict(job_id="job", worker="minimax", pid=10, title="Review recovery")
        for task, state in (("job", "running"), ("another-job", "claimed")):
            processes = parse_processes("10 1 01:30 S python3 /repo/services/dispatch_worker.py " + task + " private-token")
            work = collect_work({}, [record], processes, 10000)
            self.assertEqual(len(work), 1)
            self.assertEqual(work[0]["state"], state)
            self.assertEqual(work[0]["worker"], "minimax")
            self.assertNotIn("private-token", json.dumps(work))
            if state == "running":
                self.assertEqual(work[0]["elapsed_seconds"], 90)

    def test_collector_is_read_only_and_handles_ps_failure(self):
        with patch("worker_activity.subprocess.run", return_value=subprocess.CompletedProcess([], 0, PS, "")) as run:
            processes = process_table(Path("/unused"))
        self.assertIn(103, processes)
        self.assertEqual(run.call_args.args[0], ["/bin/ps", "-ww", "-axo", "pid=,ppid=,etime=,stat=,command="])
        for error in (OSError("missing"), subprocess.TimeoutExpired("ps", 5)):
            with patch("worker_activity.subprocess.run", side_effect=error):
                self.assertIsNone(process_table(Path("/unused")))

    def test_elapsed_days_hours_minutes_and_bad_input(self):
        for value, expected in (("01:23", 83), ("02:01:23", 7283), ("2-02:01:23", 180083), ("bad", None)):
            self.assertEqual(elapsed_seconds(value), expected)

    def test_standalone_assignment_header_is_a_title_without_prompt_details(self):
        processes = parse_processes("10 1 04:00 S codex exec Follow-up 4 on draft/webbob-clean-0927: redesign Web Bob's Jobs tab (phone-first). Private instructions and credentials follow\n")
        row = collect_work({}, [], processes, 10000)[0]
        self.assertEqual(row["title"], "redesign Web Bob's Jobs tab")
        self.assertNotIn("Private", json.dumps(row))
        self.assertNotIn("credentials", json.dumps(row))


if __name__ == "__main__":
    unittest.main()

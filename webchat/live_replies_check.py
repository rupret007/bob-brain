"""Replay the exact bad-reply session over authenticated HTTP; prove four starts."""
import json
import subprocess
import time
from pathlib import Path

from live_redeploy_check import require, observation
from providers import Redactor
from task_dispatch import task_queue

FIXTURE = Path(__file__).with_name("fixtures") / "replies_session_0927.json"
PROJECTS = ["WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football"]


def verify_replies(client, root, output, timeout=1800):
    redact = Redactor(root, client.password_file.read_text().strip())
    evidence = dict(all_pass=False, exchanges=[], started_jobs=[], source_session=json.loads(FIXTURE.read_text())["session"])
    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(redact(json.dumps(evidence, indent=2, ensure_ascii=False)) + "\n")
    try:
        client.login()
        cid = client.new()
        evidence["conversation_id"] = cid
        for index, exchange in enumerate(json.loads(FIXTURE.read_text())["exchanges"]):
            before = observation(root)
            value, answer = client.submit(cid, exchange["message"])
            after = observation(root)
            text = answer["content"]
            evidence["exchanges"].append(dict(**exchange, after=text, request_id=answer["request_id"], provider=answer["provider"]))
            require(not any(phrase in text.lower() for phrase in ("unknown task", "task details unavailable", "i'll focus", "i’ll focus")), "Unusable reply at turn " + str(index))
            if index == 0:
                require(text == "Which projects should I work on?", "Unnamed request must ask for missing targets, not promise work")
            elif index < 5:
                require(answer["provider"] == "state", "Status/criticism used a model answer")
                require(len(text.splitlines()) <= 8, "Status exceeds eight lines")
                for name in ("Codex", "Claude", "Cursor", "Gemini", "MiniMax"):
                    require(any(line.startswith(name + ":") for line in text.splitlines()), "Missing LLM: " + name)
                stable = {r.get("pid"): r for r in before["work"] if r.get("pid")}
                for row in after["work"]:
                    if row.get("pid") in stable and stable[row["pid"]]["title"] == row["title"]:
                        require(row["title"] in text, "Omitted worker: " + row["title"])
                        if not row.get("task"):
                            for field in ("screen", "log_path", "last_log_line"):
                                require(not row.get(field) or row[field] in text, "Missing worker fallback: " + field)
                codex = next(line for line in text.splitlines() if line.startswith("Codex:"))
                require("6:20" not in codex, "Claude reset time attached to Codex")
                require(not any(label in text for label in ("Chat health:", "Recent logs:", "Disk space:")), "Unrequested diagnostics")
            else:
                require(answer["provider"] == "dispatcher", "Stress action returned chat/status")
                ids = answer.get("task_ids", [])
                rows = [task_queue.tasks(root)[job] for job in ids]
                require(len(ids) == 4 and [r["title"] for r in rows] == PROJECTS, "Stress request did not create all four project jobs")
                require(len({r["requested_worker"] for r in rows}) >= 2, "Project jobs were not distributed")
                require(len(text.splitlines()) == 4 and all(job in text for job in ids), "Missing short project receipts")
                _, replay = client.submit(cid, exchange["message"], answer["request_id"])
                require(replay["task_ids"] == ids, "Replay created duplicate jobs")
                require(len([r for r in task_queue.tasks(root).values() if r["conversation_id"] == cid]) == 4, "Extra session jobs")
                evidence["task_ids"] = ids
            save()
            print("Session turn " + str(index + 1) + ": PASS", flush=True)
        deadline, last_progress = time.monotonic() + timeout, 0
        while True:
            rows = [task_queue.tasks(root)[job] for job in evidence["task_ids"]]
            evidence["jobs"] = [{key: row.get(key) for key in ("id", "title", "worker", "requested_worker", "status", "pid", "execution_started_at", "worktree", "branch", "error", "publication")} for row in rows]
            for row in rows:
                require(row["status"] not in ("failed", "cancelled"), "Stress job failed: " + row["id"] + " " + str(row.get("error")))
            started = [row for row in rows if row.get("execution_started_at") and row["status"] in ("running", "succeeded")]
            if len(started) == 4:
                break
            require(time.monotonic() < deadline, "Timed out waiting for four actual executions")
            if time.monotonic() - last_progress > 20:
                print("Stress jobs: " + ", ".join(row["title"] + "=" + row["status"] for row in rows), flush=True)
                last_progress = time.monotonic()
            save()
            time.sleep(2)
        require(len({row["worktree"] for row in rows}) == 4, "Projects share a worktree")
        for row in rows:
            require(row["worker"] in ("codex", "cursor", "claude"), "Project work lacks file tools")
            require(row["draft_pr"] and row["publish_project"] == row["title"], "Missing draft-only publication intent")
            branch = subprocess.check_output(["git", "-C", row["worktree"], "branch", "--show-current"], text=True, timeout=10).strip()
            require(branch == row["branch"] == "draft/" + row["id"], "Worker is outside its assigned draft branch")
            require((root / "conductor/state/task-runs" / row["id"] / "prompt.txt").is_file(), "Missing execution prompt")
            evidence["started_jobs"].append(dict(project=row["title"], llm=row["worker"], job_id=row["id"], worktree=row["worktree"], branch=branch, execution_started_at=row["execution_started_at"]))
        current = client.call("/api/conversations/" + cid)
        receipt = next(m for m in current["messages"] if m.get("dispatch_intent", {}).get("project_batch")) if any(m.get("dispatch_intent") for m in current["messages"]) else next(m for m in current["messages"] if m.get("task_ids") == evidence["task_ids"])
        evidence["started_reply"] = receipt["content"]
        evidence["exchanges"][-1]["after_started"] = receipt["content"]
        evidence["all_pass"] = True
    except Exception as exc:
        evidence["failure"] = str(exc)
    save()
    return evidence

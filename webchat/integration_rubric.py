"""Release rubric: actions require effects; status requires live observations."""
import json
import re
from datetime import datetime
from pathlib import Path

from dispatch_receipts import NO_DISPATCH, claims_dispatch, receipt_errors


def sessions():
    rows = json.loads(Path(__file__).with_name("fixtures").joinpath("integrate_sessions_0927.json").read_text())["sessions"]
    for session in rows:
        kinds = (["assign", "assign", "status", "status", "status", "assign", "fix"]
                 if session["source_id"].startswith("b33fac") else
                 ["missing", "status", "status", "status", "status", "projects4", "greeting", "status", "status"]
                 if session["source_id"].startswith("8126301c") else ["projects2"])
        if len(kinds) != len(session["exchanges"]):
            raise ValueError("Original session changed; review and extend the rubric before deployment")
        for exchange, kind in zip(session["exchanges"], kinds):
            exchange["expected"] = kind
    return rows


def style_errors(text, dispatch_count=0):
    prose = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    prose = re.sub(r"`webchat-[a-f0-9]{32}`", "job ID", prose)
    errors = []
    if not prose.strip():
        errors.append("empty reply")
    if len(prose.split()) > 220:
        errors.append("overlong reply")
    if len([s for s in re.split(r"[.!?](?:\s+|$)", prose) if s.strip()]) > max(4, dispatch_count):
        errors.append("too many sentences")
    if re.search(r"(?i)unknown task|task details unavailable|I['’]ll (?:focus|do better|make sure|ensure)|"
                 r"system is actively adding|ready for (?:new )?work|healthy and ready|prioritize adding work|Worker process", prose):
        errors.append("empty promise or readiness substituted for utilization")
    if re.search(r"logs/|lane-[\w-]+|\blast:|\bPID\s*[:=]|\s\|\s", prose):
        errors.append("raw diagnostic dump")
    if prose.startswith(("Yes —", "Here's the status", "I understand.")):
        errors.append("answer is not first")
    return errors


def check_reply(answer, exchange, cid, started, before, after, jobs):
    text = answer.get("content", "")
    ids = answer.get("task_ids") or ([answer["task_id"]] if answer.get("task_id") else [])
    errors = style_errors(text, len(ids))
    errors += receipt_errors(answer, jobs, cid, answer["request_id"], started)
    rows = [jobs[i] for i in ids if i in jobs]
    expected = exchange["expected"]
    if answer.get("status") != "done":
        errors.append("reply did not complete")
    if expected in ("assign", "fix", "projects2", "projects4"):
        if not ids or answer.get("provider") != "dispatcher":
            errors.append("work request has no real dispatch")
        for row in rows:
            label = row.get("title") or row["prompt"].splitlines()[0]
            if (label[:50] not in text or (row["requested_worker"] != "auto" and
                                          row["requested_worker"].lower() not in text.lower())):
                errors.append("receipt omits task or worker")
            if row["status"] in ("failed", "cancelled"):
                errors.append("accepted job failed: " + row["id"])
        if expected == "assign" and ([r["requested_worker"] for r in rows] != ["gemini", "minimax"] or
                                     [r["kind"] for r in rows] != ["audit", "test-writing"]):
            errors.append("Gemini/MiniMax did not receive API worker jobs")
        if expected == "fix" and (len(rows) != 1 or rows[0]["kind"] != "coding"):
            errors.append("fix request has no coding job")
        if expected.startswith("projects"):
            titles = ["WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football"][:int(expected[-1])]
            if [r["title"] for r in rows] != titles:
                errors.append("named projects were not dispatched")
    else:
        if ids:
            errors.append("non-action turn dispatched work")
        if expected != "status" and text != NO_DISPATCH and claims_dispatch(text):
            errors.append("unsupported dispatch claim")
    if expected == "missing" and text != "Which projects should I work on?":
        errors.append("missing project detail was not requested")
    if expected == "greeting" and re.search(r"(?i)queue|workers|services|running", text):
        errors.append("unsolicited operations report for greeting")
    if expected == "status":
        if answer.get("provider") != "state" or re.search(r"\bready\b", text, re.I):
            errors.append("status is not an authoritative utilization report")
        for worker in ("Codex", "Claude", "Cursor", "Gemini", "MiniMax"):
            if worker not in text:
                errors.append("status omits " + worker)
        from status_observation import observation_errors
        evidence_errors = observation_errors(answer, exchange["message"], cid, started,
                                             datetime.fromisoformat(after["captured_at"]).timestamp())
        errors += evidence_errors
        if evidence_errors:
            return errors
        from reply_authority import _task_name
        observed = answer["status_observation"]["snapshot"]
        for row in observed["work"]:
            if row.get("assignment_recorded") is False:
                if "CLI activity, but no recorded task" not in text:
                    errors.append("unattributed process falsely presented as assigned work")
                continue
            if _task_name(row) not in text:
                errors.append("status omits observed task " + _task_name(row))
            if row.get("model") and row["model"] not in text:
                errors.append("status omits observed model " + row["model"])
        if text.count("running for") != observed["work_counts"]["running"]:
            errors.append("status running count disagrees with observed execution")
        for row in observed["queue_jobs"]["queued"]:
            if _task_name(row) not in text:
                errors.append("status omits waiting assignment " + _task_name(row))
    return errors


def run_eval(*, project_lane_only=False):
    """Run the same exact-message rubric offline against real isolated journals."""
    import tempfile
    import time
    import uuid
    from unittest.mock import patch
    from app import Chat
    from live_status_snapshot import build_live_status_snapshot
    from task_dispatch import task_queue

    class Greeting:
        def reply(self, *args):
            return dict(content="Hi Jeff!", provider="gemini", attempts=[])

    # Attempt 2205 had these open screens but zero queued/claimed jobs and no
    # confirmed worker. Exercise collection and dispatch without a seed job.
    screens = ({"lane-integrate-deploy-2205": "68531.lane-integrate-deploy-2205",
                "lane-webbob-llm-reviews": "29817.lane-webbob-llm-reviews"}
               if project_lane_only else {})
    results = []
    with tempfile.TemporaryDirectory() as folder, \
            patch("live_status_snapshot._screen_sessions", return_value=screens), \
            patch("live_status_snapshot.process_table", return_value={}):
        root = Path(folder)
        chat = Chat(root / "conductor/webchat", root, Greeting())
        try:
            if not project_lane_only:
                task_queue.enqueue(root, "external", "source", "Improve WebJam recording reliability", worker="codex", kind="coding", title="WebJam")
            for source in sessions():
                cid = chat.new_conversation()["id"]
                for index, exchange in enumerate(source["exchanges"]):
                    before = build_live_status_snapshot(root)
                    started = time.time()
                    chat.submit(cid, exchange["message"], str(uuid.uuid4()))
                    thread = chat.workers.get(cid)
                    if thread:
                        thread["thread"].join(5)
                    answer = chat.get(cid)["messages"][-1]
                    errors = check_reply(answer, exchange, cid, started, before, build_live_status_snapshot(root), task_queue.tasks(root))
                    results.append(dict(name=source["source_id"][:8] + " turn " + str(index + 1) +
                                             (" (unverified project lane)" if project_lane_only else ""),
                                        pass_check=not errors, errors=errors, reply=answer["content"]))
        finally:
            chat.close()
    return results

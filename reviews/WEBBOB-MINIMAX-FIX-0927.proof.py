"""Run isolated worker calls; export keys beforehand, pass the code checkout path.

Only the temporary root is mutated. Live ledger snapshots preserve budget limits;
the successful worker calls use the real launcher and transport. Negative cases
explicitly replay a historical refusal or inject an unrelated candidate answer.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

code = Path(sys.argv[1]).resolve()
live = code.parent / "conductor"
output = code / "reviews/WEBBOB-MINIMAX-FIX-0927.evidence.json"
isolated = Path(tempfile.mkdtemp(prefix="webbob-minimax-proof-0927-"))
os.environ["BOB_ROOT"] = str(isolated)
os.environ["BOB_WEBCHAT_DIR"] = str(isolated / "conductor/webchat")
sys.path[:0] = [str(code / "services"), str(code / "state"), str(code / "webchat")]
# Carry current spending forward without writing any live ledger or queue.
for name in ("ledger/minimax.jsonl", "ledger/gemini.jsonl", "webjam-ux/spend.log"):
    source = live / name
    if source.exists():
        dest = isolated / "conductor" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)

import budget
import dispatch_worker
import task_queue
from app import Chat

class NoChatGeneration:
    def health(self, conversation_id=None):
        return {"providers": {}, "order": [], "fast_order": []}
    def reply(self, *args):
        raise AssertionError("Only worker jobs belong in this proof")

def listener():
    pid = subprocess.check_output(["lsof", "-tiTCP:8787", "-sTCP:LISTEN"], text=True).strip()
    return subprocess.check_output(["ps", "-p", pid, "-o", "pid=,lstart=,command="], text=True).strip()

evidence = dict(started_at=time.time(), code_root=str(code), isolated_root=str(isolated),
                live_listener_before=listener(), cases=[], initial_spend={w: budget.totals(w) for w in task_queue.API_WORKERS})
evidence["implementation_sha256"] = {name: hashlib.sha256((code / name).read_bytes()).hexdigest() for name in (
    "services/dispatch_worker.py", "services/lanes.py", "services/result_acceptance.py", "state/task_queue.py",
    "webchat/task_dispatch.py", "webchat/max_mode.py")}
folder = isolated / "conductor/webchat"
folder.mkdir(parents=True, exist_ok=True)
chat = Chat(folder, isolated, NoChatGeneration())
conversation = chat.new_conversation()["id"]

def run_case(name, worker, prompt, expected, injected=None, real_review=False):
    submitted = chat.submit(conversation, "start a job: " + prompt, str(uuid.uuid4()), worker=worker)
    identifier = submitted["messages"][-1]["task_id"]
    row = task_queue.claim(isolated, worker, identifier=identifier)
    started = time.monotonic()
    if injected is None:
        # Real launcher, real credential loading and transport; no worker mocks.
        process = subprocess.run(["bash", str(code / "services/dispatch-worker.sh"), identifier, row["claim_token"]],
                                 capture_output=True, text=True, timeout=300)
        exit_code = process.returncode
    else:
        ask = dispatch_worker.ask
        def response(*args, **kwargs):
            if kwargs.get("purpose") == "result-acceptance" and real_review:
                return ask(*args, **kwargs)
            return injected
        with patch.object(dispatch_worker, "ask", side_effect=response):
            exit_code = dispatch_worker.execute(identifier, row["claim_token"])
    chat.reconcile_tasks()
    result = task_queue.tasks(isolated)[identifier]
    messages = [m for m in chat.history(conversation)["messages"] if m.get("task_id") == identifier and m.get("task_status")]
    events = [json.loads(line) for line in (isolated / "conductor/state/queue.jsonl").read_text().splitlines()
              if json.loads(line)["id"] == identifier]
    item = dict(name=name, worker=worker, injected_answer=injected is not None, real_acceptance_review=real_review or injected is None,
                elapsed_seconds=round(time.monotonic()-started, 3), exit_code=exit_code, queue=result, messages=messages, events=events)
    evidence["cases"].append(item)
    output.write_text(dispatch_worker.redact(json.dumps(evidence, indent=2)) + "\n")
    assert result["status"] == expected, result.get("error")
    assert len(messages) == 1 and messages[0]["task_status"] == expected
    assert result["attempts"] == 1 and result["delivered_at"]
    result_file = isolated / "conductor/state/task-runs" / identifier / "RESULT.md"
    if expected == "succeeded":
        assert exit_code == 0
        assert result["acceptance"]["accepted"] is True
        assert result["worktree"] is None and result["branch"] is None
        assert result_file.read_text() == result["result"] + "\n"
        assert result["result_sha256"] == hashlib.sha256(result["result"].encode()).hexdigest()
        assert "finished on " + worker in messages[0]["content"]
    else:
        assert exit_code == 1 and not result_file.exists()
        assert not any(event["status"] == "succeeded" for event in events)
        assert "finished on" not in messages[0]["content"]
    print(json.dumps({"case": name, "status": result["status"], "id": identifier,
                      "seconds": item["elapsed_seconds"], "answer": result.get("result", result.get("error"))}), flush=True)

try:
    marker = "WEBBOB-MINIMAX-FIX-0927-" + uuid.uuid4().hex[:8]
    for worker in ("minimax", "gemini"):
        prompt = "write one sentence confirming you ran, into your answer. Include the exact phrase '" + marker + " " + worker + "'."
        run_case("real-confirmation-" + worker, worker, prompt, "succeeded")
    original = (live / "state/task-runs/webchat-d54cc740a7765f8e9def8b7e47caa0b8/RESULT.md").read_text().strip()
    run_case("incident-refusal-replay", "minimax",
             "write one sentence confirming you ran, into your answer. Include the exact phrase 'WEBBOB-VERIFY5-0927-d8f5a3e9 minimax'.",
             "failed", original)
    run_case("off-topic-real-review", "minimax",
             "Calculate 12 + 18 and give the sum. Include the exact phrase '" + marker + " off-topic'.",
             "failed", "Tomatoes grow best with enough sunlight and regular watering. " + marker + " off-topic", True)
    for worker in ("minimax", "gemini"):
        value = chat.submit(conversation, "start a job: Read services/dispatch_worker.py and summarize it.", str(uuid.uuid4()), worker=worker)
        message = value["messages"][-1]
        assert message["action_card"]["state"] == "refused" and "API-only" in message["content"]
        evidence["cases"].append(dict(name="file-limit-" + worker, message=message))
    assert not (isolated / "workspaces").exists()
    evidence["live_listener_after"] = listener()
    assert evidence["live_listener_before"] == evidence["live_listener_after"]
    evidence["final_spend"] = {worker: budget.totals(worker) for worker in task_queue.API_WORKERS}
    evidence["finished_at"] = time.time()
    evidence["passed"] = True
finally:
    chat.close()
    output.write_text(dispatch_worker.redact(json.dumps(evidence, indent=2)) + "\n")
print("PASS: isolated proof; live listener unchanged; evidence saved", flush=True)

#!/usr/bin/env python3
"""Bounded live code review; model calls only, no messaging or deployment."""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

lane, checkout, prompt_file, output_file, expected = sys.argv[1:]
if lane not in ("gemini", "minimax"):
    raise SystemExit("Only Gemini and MiniMax are allowed")
checkout, prompt_file, output_file = map(Path, (checkout, prompt_file, output_file))
actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
if actual != expected:
    raise SystemExit("Review tip changed")
if subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain"], text=True).strip():
    raise SystemExit("Review checkout must be clean")
os.environ["BOB_ROOT"] = "/Users/jeffstory/Documents/bob-overnight-inject"
sys.path.insert(0, str(checkout / "services"))
from lanes import ask
from api_tasks import MODELS
from state import atomic_write
prompt = prompt_file.read_text()
metadata = {"lane": lane, "model": MODELS[lane], "reviewed_sha": actual,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "started_at": datetime.now(timezone.utc).isoformat(), "status": "REQUESTED"}
receipt = output_file.with_suffix(".json")
atomic_write(receipt, json.dumps(metadata, indent=2) + "\n")
try:
    result = ask(lane, prompt, purpose="webbob-instinct-review")
    lines = [line.strip() for line in result.splitlines() if line.strip()]
    verdicts = re.findall(r"^VERDICT: (PASS|BLOCKED)$", result, flags=re.M)
    verdict = verdicts[0] if len(verdicts) == 1 and lines[-1] == "VERDICT: " + verdicts[0] else "INVALID"
    if "REVIEWED_SHA: " + actual not in result:
        verdict = "INVALID"
    metadata.update(status="COMPLETE", verdict=verdict)
    atomic_write(output_file, f"# LIVE {lane.upper()} Instinct review 0810\n\nTip: {actual}\nModel: {MODELS[lane]}\nPrompt SHA256: {metadata['prompt_sha256']}\n\n" + result + "\n")
except Exception as exc:
    reason = str(exc) if isinstance(exc, (RuntimeError, BlockingIOError)) else type(exc).__name__
    metadata.update(status="BLOCKED", reason=reason)
    atomic_write(output_file, f"# LIVE {lane.upper()} Instinct review 0810\n\nTip: {actual}\nStatus: BLOCKED\nReason: {reason}\nNo pass claimed.\n")
metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
atomic_write(receipt, json.dumps(metadata, indent=2) + "\n")
print(json.dumps(metadata))
raise SystemExit(0 if metadata.get("verdict") == "PASS" else 1)

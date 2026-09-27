"""Call the scheduler in a separate process, with an explicit state root."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from providers import ProviderError, clean_env, run


def start_request(root: Path, identifier: str, *, cancel=None) -> dict:
    env = clean_env()
    env["BOB_ROOT"] = str(root.resolve())
    script = Path(__file__).resolve().parents[1] / "services/dispatch_request.py"
    try:
        code, out, _ = run([sys.executable, str(script), identifier], cwd=root, env=env,
                           cancel=cancel or threading.Event(), timeout=45)
        if code:
            raise ValueError("scheduler dispatch failed")
        result = json.loads(out)
        if not isinstance(result, dict) or result.get("queue_id") != identifier:
            raise ValueError("invalid scheduler receipt")
        return result
    except (OSError, ValueError, ProviderError):
        # The enqueue has already committed. An uncertain launch must not requeue it.
        return {"queue_id": identifier, "started": False,
                "reason": "Lane start is unconfirmed; the job is saved. Check Jobs for its receipt."}

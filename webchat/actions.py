"""Durable once-only confirmation receipts, outside the provider retry path."""
import fcntl
import hashlib
import json

from failover import atomic_json
from job_queue import queue_draft


def queue_once(root, action_id, description):
    folder = root / "conductor/webchat/sessions"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / "action-receipts.json"
    fingerprint = hashlib.sha256(description.encode()).hexdigest()
    with (folder / "action-receipts.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipts = json.loads(path.read_text()) if path.exists() else {}
        existing = receipts.get(action_id)
        if existing:
            if existing["fingerprint"] != fingerprint:
                return {"ok": False, "error": "This confirmation belongs to a different job."}
            if existing["state"] == "done":
                return existing["result"]
            return {"ok": False, "error": "This confirmation already started a job submission. Check Jobs before making another request; it will not run twice."}
        receipts[action_id] = {"fingerprint": fingerprint, "state": "claimed"}
        atomic_json(path, receipts)  # Persist BEFORE any queue/file side effect.
        try:
            result = queue_draft(root, description)
        except Exception:
            # Leave the durable claim: an ambiguous partial write cannot cause
            # the original confirmation to be executed a second time.
            return {"ok": False, "error": "Job submission was interrupted. Check Jobs before retrying; this confirmation will not run twice."}
        receipts[action_id].update(state="done", result=result)
        atomic_json(path, receipts)
        return result

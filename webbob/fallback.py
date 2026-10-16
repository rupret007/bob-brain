"""Render-only fallback notice; never dispatches work or forwards private data."""
import math
import time


def fallback_notice(health, now=None, freshness=120):
    now = time.time() if now is None else now
    health = health if isinstance(health, dict) else {}
    unavailable, unknown = [], []
    for bot, label in (("webbob", "Web Bob"), ("mini", "Mini")):
        row = health.get(bot, {})
        row = row if isinstance(row, dict) else {}
        observed = row.get("observed_at")
        if (type(observed) not in (int, float) or not math.isfinite(observed)
                or not 0 <= now - observed <= freshness or row.get("status") not in ("up", "down")):
            unknown.append(label)
        elif row["status"] == "down":
            unavailable.append(label)
    if not unavailable and not unknown:
        return None
    reasons = []
    if unavailable:
        reasons.append(" and ".join(unavailable) + (" are unavailable." if len(unavailable) > 1 else " is unavailable."))
    if unknown:
        reasons.append("Could not verify " + " and ".join(unknown) + " availability.")
    return {"kind": "fallback_notice", "message": " ".join(reasons) + " Continue with Grok Bot if it is available. Your existing work stays here.",
            "action": "open_grok_bot_manually", "auto_forward": False}

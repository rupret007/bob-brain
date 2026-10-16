"""One static status view from explicit observations, with no runtime control."""
from html import escape
import math
import time

BOTS = {"bob": "Grok Bot", "webbob": "Web Bob", "andrea": "Andrea", "karen": "Karen"}


def status_rows(observations, now=None, max_age=120):
    now = time.time() if now is None else now
    rows = []
    for bot, label in BOTS.items():
        observed = observations.get(bot, {})
        at = observed.get("observed_at")
        fresh = type(at) in (int, float) and math.isfinite(at) and 0 <= now - at <= max_age
        state = observed.get("state")
        if not fresh or state not in {"up", "down", "degraded"}:
            state = "unknown"
        # Only these scalar facts leave the status boundary. Ignore logs,
        # private inbox bodies, credentials, conversation content and prompts.
        pending = observed.get("pending")
        rows.append({"bot": bot, "label": label, "state": state,
                     "age_seconds": round(now - at) if fresh else None,
                     "pending": pending if fresh and type(pending) is int and pending >= 0 else None,
                     "review": observed.get("review") if fresh and observed.get("review") in {"PASS", "FAIL", "PENDING"} else "UNKNOWN"})
    return rows


def render_status(observations, now=None):
    rows = status_rows(observations, now)
    html = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
            '<title>All-bot status</title><main><h1>All-bot status</h1><p>Observed health only. Review status does not authorize a release.</p>',
            '<table><thead><tr><th>Bot</th><th>Health</th><th>Observation age</th><th>Pending</th><th>Review</th></tr></thead><tbody>']
    for row in rows:
        values = [row["label"], row["state"], str(row["age_seconds"]) + " s" if row["age_seconds"] is not None else "unknown",
                  str(row["pending"]) if row["pending"] is not None else "unknown", row["review"]]
        html.append("<tr>" + "".join("<td>" + escape(value) + "</td>" for value in values) + "</tr>")
    html.append('</tbody></table><p>Web Bob or Mini unavailable? Continue with Grok Bot if available. No work is forwarded automatically.</p></main></html>')
    return "\n".join(html)

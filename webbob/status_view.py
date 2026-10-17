"""One static status view from explicit observations, with no runtime control."""
from html import escape
import math
import time

from webbob.fallback_copy import GROK_STATUS_FOOTER

BOTS = {"bob": "Grok Bot", "webbob": "Web Bob", "andrea": "Andrea", "karen": "Karen"}


def status_rows(observations, now=None, max_age=120):
    now = time.time() if now is None else now
    observations = observations if isinstance(observations, dict) else {}
    rows = []
    for bot, label in BOTS.items():
        observed = observations.get(bot, {})
        observed = observed if isinstance(observed, dict) else {}
        at = observed.get("observed_at")
        fresh = type(at) in (int, float) and math.isfinite(at) and 0 <= now - at <= max_age
        state = observed.get("state")
        if not fresh or state not in ("up", "down", "degraded"):
            state = "unknown"
        # Only these scalar facts leave the status boundary. Ignore logs,
        # private inbox bodies, credentials, conversation content and prompts.
        pending = observed.get("pending")
        rows.append({"bot": bot, "label": label, "state": state,
                     "age_seconds": round(now - at) if fresh else None,
                     "pending": pending if fresh and type(pending) is int and pending >= 0 else None,
                     "review": observed.get("review") if fresh and observed.get("review") in ("PASS", "FAIL", "PENDING") else "UNKNOWN"})
    return rows


def _pct_label(value):
    if value is None:
        return "unknown"
    if type(value) not in (int, float) or not math.isfinite(value):
        return "unknown"
    return f"{value:g}%"


def capacity_rows(capacity_doc):
    capacity_doc = capacity_doc if isinstance(capacity_doc, dict) else {}
    rows_out = []
    for row in capacity_doc.get("rows") or []:
        if not isinstance(row, dict):
            continue
        provider = row.get("provider")
        if not isinstance(provider, str) or not provider:
            provider = "unknown"
        rows_out.append({
            "provider": provider,
            "used_pct": _pct_label(row.get("used_pct")),
            "remaining_pct": _pct_label(row.get("remaining_pct")),
            "reset_ct": row.get("reset_ct") if isinstance(row.get("reset_ct"), str) and row.get("reset_ct") else "unknown",
            "freshness": row.get("freshness") if isinstance(row.get("freshness"), str) and row.get("freshness") else "unknown",
            "status": row.get("status") if isinstance(row.get("status"), str) and row.get("status") else "unknown",
        })
    return rows_out


def render_capacity(capacity_doc):
    rows = capacity_rows(capacity_doc)
    stale = bool((capacity_doc or {}).get("snapshot_stale"))
    note = (capacity_doc or {}).get("snapshot_note") or ""
    html = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
            '<title>AI capacity</title><main><h1>AI capacity</h1>',
            '<p>Provider usage only. Percentages may be unknown when not exposed locally.</p>']
    if stale:
        html.append("<p>Snapshot stale: " + escape(note or "refresh unavailable") + "</p>")
    html += ['<table><thead><tr><th>Provider</th><th>Used</th><th>Remaining</th><th>Reset (CT)</th><th>Fresh</th><th>Status</th></tr></thead><tbody>']
    for row in rows:
        values = [row["provider"], row["used_pct"], row["remaining_pct"], row["reset_ct"], row["freshness"], row["status"]]
        html.append("<tr>" + "".join("<td>" + escape(str(value)) + "</td>" for value in values) + "</tr>")
    html.append("</tbody></table></main></html>")
    return "\n".join(html)


def render_status(observations, now=None):
    rows = status_rows(observations, now)
    html = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
            '<title>All-bot status</title><main><h1>All-bot status</h1><p>Observed health only. Review status does not authorize a release.</p>',
            '<table><thead><tr><th>Bot</th><th>Health</th><th>Observation age</th><th>Pending</th><th>Review</th></tr></thead><tbody>']
    for row in rows:
        values = [row["label"], row["state"], str(row["age_seconds"]) + " s" if row["age_seconds"] is not None else "unknown",
                  str(row["pending"]) if row["pending"] is not None else "unknown", row["review"]]
        html.append("<tr>" + "".join("<td>" + escape(value) + "</td>" for value in values) + "</tr>")
    html.append(f"</tbody></table><p>{escape(GROK_STATUS_FOOTER)}</p></main></html>")
    return "\n".join(html)

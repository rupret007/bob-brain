#!/usr/bin/env python3
"""Fsynced per-lane reservations; unknown/failed calls retain their worst-case cost."""
from __future__ import annotations

import json
import os
import time
import uuid

from state import CONDUCTOR, _append, _rows, lock, read_json

LANES = ("codex", "claude", "cursor", "gemini", "minimax", "mini")
CAP_USD = 48.0
GEMINI_CAP_USD = 48.0
# USD / million tokens, verified against provider pricing on 2026-09-26.
RATES = {"minimax": (0.30, 1.20, 0.06, 0.375), "gemini": (0.30, 2.50, 0.03, 0.30)}


class BudgetExceeded(RuntimeError):
    pass


def cap(lane):
    default = {"minimax": CAP_USD, "gemini": GEMINI_CAP_USD}.get(lane)
    if default is None:
        return None
    # Runtime configuration may tighten the standing ceiling, never raise it.
    return max(0, min(default, float(os.environ.get("BOB_" + lane.upper() + "_CAP_USD", default))))


def status(lane):
    data = totals(lane)
    limit = data["cap_usd"]
    fraction = data["committed_usd"] / limit if limit else (1 if limit == 0 else None)
    if limit is None and lane != "mini":
        # Plan percentages must come from an observed provider quota, not from
        # dollar estimates or token counts that cannot describe a subscription.
        quota = read_json(CONDUCTOR / "plan-usage.json", {}).get(lane, {})
        if quota.get("reset_at", float("inf")) > time.time() and "used_percent" in quota:
            fraction = max(0, float(quota["used_percent"]) / 100)
    tier = ("stop" if fraction is not None and fraction >= .95 else
            "slow" if fraction is not None and fraction >= .85 else
            "warn" if fraction is not None and fraction >= .70 else "normal")
    return dict(data, tier=tier, used_percent=round(fraction * 100, 2) if fraction is not None else None,
                quota_known=fraction is not None or lane == "mini")


def check(lane):
    usage = status(lane)
    if usage["tier"] == "stop":
        raise BudgetExceeded(lane + " stopped at 95% of its usage cap")
    return usage


def path(lane):
    if lane not in LANES:
        raise ValueError("unknown lane")
    folder = CONDUCTOR / "ledger"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / (lane + ".jsonl")


def totals(lane):
    with lock("ledger-" + lane):
        calls = {r["call_id"]: r for r in _rows(path(lane))}
        settled = sum(r.get("cost_usd", 0) or 0 for r in calls.values())
        reserved = sum(r.get("reserved_usd", 0) for r in calls.values() if r.get("cost_usd") is None)
        return {"spent_usd": round(settled, 8), "reserved_usd": round(reserved, 8),
                "committed_usd": round(settled + reserved, 8), "calls": len(calls),
                "cap_usd": cap(lane)}


def reserve(lane, prompt, max_tokens, purpose="model", *, model_id=None, google_search=False):
    if lane == "minimax":
        import_ux_ledger()
    # Reserve the Pro long-context tier conservatively; settle at the actual tier.
    rate = (2.50, 15.0, .25, 2.50) if model_id == "gemini-2.5-pro" else RATES[lane]
    search_cost = .035 if google_search else 0
    bound = ((len(prompt.encode("utf-8")) + 4096) * max(rate[0], rate[3]) + max_tokens * rate[1]) / 1_000_000 + search_cost
    with lock("ledger-" + lane):
        calls = {r["call_id"]: r for r in _rows(path(lane))}
        committed = sum(r["cost_usd"] if r.get("cost_usd") is not None else r.get("reserved_usd", 0) for r in calls.values())
        if committed + bound > cap(lane) * .95:
            raise BudgetExceeded(lane + " 95% cap: next worst-case request does not fit")
        row = {"call_id": uuid.uuid4().hex, "event": "reserved", "lane": lane,
               "reserved_usd": bound, "cost_usd": None, "purpose": purpose, "timestamp": time.time(),
               "model": model_id, "search_cost_usd": search_cost}
        _append(path(lane), row)
        return row


def settle(lane, reservation, data):
    usage = data.get("usage", {}) if lane == "minimax" else data.get("usageMetadata", {})
    cost = None
    if lane == "minimax" and all(k in usage for k in ("prompt_tokens", "completion_tokens")):
        inp, out = usage["prompt_tokens"], usage["completion_tokens"]
        details = usage.get("prompt_tokens_details") or {}
        cached = details.get("cached_tokens", usage.get("cache_read_input_tokens", 0))
        written = usage.get("cache_creation_input_tokens", 0)
        # Cache creation may be separate from prompt_tokens; charging it separately
        # is conservative and avoids undercounting incompatible response schemas.
        cost = (max(0, inp - cached) * .30 + out * 1.20 + cached * .06 + written * .375) / 1_000_000
    elif lane == "gemini" and "promptTokenCount" in usage:
        inp, out = ((2.50, 15.0) if usage["promptTokenCount"] > 200000 else (1.25, 10.0)) if reservation.get("model") == "gemini-2.5-pro" else (.30, 2.50)
        cost = (usage["promptTokenCount"] * inp +
                (usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)) * out) / 1_000_000
        # Do not assume this account has any free grounding allowance left.
        cost += reservation.get("search_cost_usd", 0)
    if cost is not None and (cost < 0 or cost > reservation["reserved_usd"]):
        # Retain the larger charge and stop further calls if the provider violated
        # the bound. Never discard billing evidence to make the cap look healthy.
        cost = max(cost, reservation["reserved_usd"])
    with lock("ledger-" + lane):
        _append(path(lane), dict(reservation, event="response", cost_usd=cost, usage=usage,
                                response_id=data.get("id"), timestamp=time.time()))


def record_cli(lane, events, ok, purpose):
    usage = {}
    reported_cost = None
    for event in events:
        if isinstance(event.get("usage"), dict):
            usage = event["usage"]
        if event.get("total_cost_usd") is not None:
            reported_cost = event["total_cost_usd"]
    with lock("ledger-" + lane):
        _append(path(lane), {"call_id": uuid.uuid4().hex, "lane": lane, "event": "cli",
                            "usage": usage, "cost_usd": reported_cost, "reserved_usd": 0,
                            "billing": "CLI plan; dollar cost unavailable" if reported_cost is None else "CLI reported cost",
                            "ok": ok, "purpose": purpose, "timestamp": time.time()})


def import_ux_ledger():
    source = CONDUCTOR / "webjam-ux/spend.log"
    if not source.exists():
        return
    calls = {}
    for line in source.read_text().splitlines():
        row = json.loads(line)
        calls[row["pass"]] = row
    with lock("ledger-minimax"):
        known = {r["call_id"] for r in _rows(path("minimax"))}
        for name, row in calls.items():
            call_id = "legacy-ux-" + name
            if call_id not in known:
                _append(path("minimax"), dict(row, call_id=call_id, lane="minimax", event="imported",
                                             timestamp=time.time()))

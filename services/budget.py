#!/usr/bin/env python3
"""Fsynced per-lane reservations; unknown/failed calls retain their worst-case cost."""
from __future__ import annotations

import json
import time
import uuid

from state import CONDUCTOR, _append, _rows, lock

LANES = ("codex", "claude", "cursor", "gemini", "minimax")
CAP_USD = 48.0
# USD / million tokens, verified against provider pricing on 2026-09-26.
RATES = {"minimax": (0.30, 1.20, 0.06, 0.375), "gemini": (0.30, 2.50, 0.03, 0.30)}


class BudgetExceeded(RuntimeError):
    pass


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
                "cap_usd": CAP_USD if lane == "minimax" else None}


def reserve(lane, prompt, max_tokens, purpose="model"):
    if lane == "minimax":
        import_ux_ledger()
    rate = RATES[lane]
    bound = ((len(prompt.encode("utf-8")) + 4096) * max(rate[0], rate[3]) + max_tokens * rate[1]) / 1_000_000
    with lock("ledger-" + lane):
        calls = {r["call_id"]: r for r in _rows(path(lane))}
        committed = sum(r["cost_usd"] if r.get("cost_usd") is not None else r.get("reserved_usd", 0) for r in calls.values())
        if lane == "minimax" and committed + bound > CAP_USD:
            raise BudgetExceeded("MiniMax $48 cap: next worst-case request does not fit")
        row = {"call_id": uuid.uuid4().hex, "event": "reserved", "lane": lane,
               "reserved_usd": bound, "cost_usd": None, "purpose": purpose, "timestamp": time.time()}
        _append(path(lane), row)
        return row


def abandon(lane, reservation, reason="transport-failed"):
    """Charge the worst-case reservation when a metered call never returned a response."""
    with lock("ledger-" + lane):
        _append(path(lane), dict(reservation, event="abandoned", cost_usd=reservation["reserved_usd"],
                                reason=reason, timestamp=time.time()))


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
        cost = (usage["promptTokenCount"] * .30 +
                (usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)) * 2.50) / 1_000_000
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

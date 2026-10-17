#!/usr/bin/env python3
"""Fsynced per-lane reservations; unknown/failed calls retain their worst-case cost."""
from __future__ import annotations

import json
import math
import os
import time
import uuid
import sys
from pathlib import Path

from state import CONDUCTOR, _append, _rows, lock, read_json, write_json
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'state'))
import generation_budget

LANES = ("codex", "claude", "cursor", "gemini", "minimax", "mini")
CAP_USD = 48.0
# Owner authorization 2026-10-01: use Gemini until prepaid credit needs refill.
# None removes the old local ceiling, not metering or provider funding limits.
GEMINI_CAP_USD = None
# USD / million tokens, verified against provider pricing on 2026-09-26.
RATES = {"minimax": (0.30, 1.20, 0.06, 0.375), "gemini": (0.30, 2.50, 0.03, 0.30)}


class BudgetExceeded(RuntimeError):
    pass


class RefillRequired(BudgetExceeded):
    def __init__(self):
        super().__init__('Gemini funding needs attention (payment or credit refill); automatic attempts are stopped')


def funding(lane):
    data = read_json(CONDUCTOR / 'gemini-funding.json', {}) if lane == 'gemini' else {}
    if not isinstance(data, dict) or type(data.get('refill_required', False)) is not bool:
        raise ValueError('Invalid provider funding observation')
    return data


def mark_refill_required():
    with lock('ledger-gemini'):
        prior = funding('gemini')
        if not prior.get('refill_required'):
            write_json(CONDUCTOR / 'gemini-funding.json', dict(
                refill_required=True, observed_at=time.time(),
                source='Explicit Gemini payment-required/depleted-credit response',
                prior_retry={k: prior[k] for k in ('retry_authorized_at', 'note') if k in prior}))


def authorize_refill_retry(note):
    """Operator action after owner refill confirmation; never a background probe."""
    if not isinstance(note, str) or not note.strip():
        raise ValueError('Record the owner refill/retry instruction')
    with lock('ledger-gemini'):
        prior = funding('gemini')
        write_json(CONDUCTOR / 'gemini-funding.json', dict(
            refill_required=False, retry_authorized_at=time.time(), note=note[:600],
            previous_observation={k: prior[k] for k in ('observed_at', 'source') if k in prior},
            balance_verified=False))


def cap(lane):
    default = {"minimax": CAP_USD, "gemini": GEMINI_CAP_USD}.get(lane)
    if lane not in RATES:
        return None
    value = os.environ.get("BOB_" + lane.upper() + "_CAP_USD")
    if value is None:
        return default
    configured = float(value)
    if not math.isfinite(configured):
        raise ValueError('Local budget ceiling must be finite')
    # A runtime ceiling may tighten either a finite ceiling or prepaid policy.
    return max(0, configured if default is None else min(default, configured))


def status(lane):
    data = totals(lane)
    limit = data["cap_usd"]
    fraction = data["committed_usd"] / limit if limit else (1 if limit == 0 else None)
    if limit is None and lane not in (*RATES, 'mini'):
        # Plan percentages must come from an observed provider quota, not from
        # dollar estimates or token counts that cannot describe a subscription.
        quota = read_json(CONDUCTOR / "plan-usage.json", {}).get(lane, {})
        if quota.get("reset_at", float("inf")) > time.time() and "used_percent" in quota:
            fraction = max(0, float(quota["used_percent"]) / 100)
    tier = ("stop" if fraction is not None and fraction >= .95 else
            "slow" if fraction is not None and fraction >= .85 else
            "warn" if fraction is not None and fraction >= .70 else "normal")
    refill = bool(funding(lane).get('refill_required'))
    return dict(data, tier='stop' if refill else tier,
                reason='refill_required' if refill else None, refill_required=refill,
                provider_balance_known=False if lane in RATES else None,
                used_percent=round(fraction * 100, 2) if fraction is not None else None,
                quota_known=fraction is not None or lane == "mini")


def check(lane):
    usage = status(lane)
    if usage.get('refill_required'):
        raise RefillRequired()
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
    # Gemini3.8 has promotional rates through2026. Reserve the published
    # post-promotion rates even now so the bound also covers a date transition.
    rate = ((1.50, 7.50, .15, 1.50) if model_id == 'gemini-3.8-flash' else
            (2.50, 15.0, .25, 2.50) if model_id == "gemini-2.5-pro" else RATES[lane])
    search_cost = .035 if google_search else 0
    bound = ((len(prompt.encode("utf-8")) + 4096) * max(rate[0], rate[3]) + max_tokens * rate[1]) / 1_000_000 + search_cost
    with lock("ledger-" + lane):
        if funding(lane).get('refill_required'):
            raise RefillRequired()
        calls = {r["call_id"]: r for r in _rows(path(lane))}
        committed = sum(r["cost_usd"] if r.get("cost_usd") is not None else r.get("reserved_usd", 0) for r in calls.values())
        limit = cap(lane)
        if limit is not None and committed + bound > limit * .95:
            raise BudgetExceeded(lane + " 95% cap: next worst-case request does not fit")
        row = {"call_id": uuid.uuid4().hex, "event": "reserved", "lane": lane,
               "reserved_usd": bound, "cost_usd": None, "purpose": purpose, "timestamp": time.time(),
               "model": model_id, "search_cost_usd": search_cost}
        try:
            # Always lane -> goal lock order. Transport needs both reservations.
            row['goal_reservation'] = generation_budget.reserve(lane, bound, call_id=row['call_id'],env=dict(os.environ,BOB_ROOT=str(CONDUCTOR.parent)))
        except generation_budget.AdmissionDenied as exc:
            raise BudgetExceeded(str(exc)) from None
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
        if reservation.get('model') == 'gemini-3.8-flash':
            # Pricing: ai.google.dev/gemini-api/docs/pricing, checked2026-10-01.
            # Settlement at/after2027 uses the higher published rates, including
            # calls begun before midnight. Cached input is conservatively billed
            # as uncached, matching the existing local estimate convention.
            inp, out = (.75, 3.75) if time.time() < 1798761600 else (1.50, 7.50)
        cost = (usage["promptTokenCount"] * inp +
                (usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)) * out) / 1_000_000
        # Do not assume this account has any free grounding allowance left.
        cost += reservation.get("search_cost_usd", 0)
    if cost is not None and (cost < 0 or cost > reservation["reserved_usd"]):
        # Retain the larger charge and stop further calls if the provider violated
        # the bound. Never discard billing evidence to make the cap look healthy.
        cost = max(cost, reservation["reserved_usd"])
    with lock("ledger-" + lane):
        generation_budget.settle(reservation.get('goal_reservation'), cost, usage=usage)
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

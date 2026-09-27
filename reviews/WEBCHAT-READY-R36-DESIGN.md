# Web Bob Round 36 — design note (research-first, on R14/R35 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R14 final `2187237` / R35 `d025af6` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| ADDED 02:03 dashboard | `enrich_live_ops_bundle` + `dashboard_plain[]` on Jobs + Pages | Raw log dumps in chat | Jeff cannot see terminal |
| ADDED 04:18 P0 | `parse_do_more` + conductor RULES (not read-only) | Telling Jeff to queue himself | Replay "do more" |
| R14 council | Natural council asks (`Ask the council to …`) | `run council on:` in chips | Phone plain English |
| Jeff 02:00 music | Lyrics/coaches only ($0) | MiniMax music API | 410 not entitled |
| Failover TOP | `WEBCHAT_HANDBACK_TAG=r36` ×2 isolated | Prod ledger mutation | Zero lost context |

## R36 build focus (lowest scores first)

1. **Failover (TOP):** handback drill ×2 (`r36-1`, `r36-2`), `prod_unchanged: true`, reverse + `events_ok`.
2. **Dashboard (02:03):** Ship `dashboard_plain` grid on Jobs tab; Ops snapshot Unknown/stale; weakest + headroom row.
3. **Conductor parity (9.97):** Restore `parse_do_more`, provider RULES, `overlay_pins` for drill continuity.
4. **Voice (9.96–9.98):** Mic + call button contrast (44pt, ring).
5. **Music ($0):** Parity cases for natural council + do-more routing; refrain coach inherited.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote on disagreements; no Grok.

# Web Bob Round 34 — design note (research-first, on R33)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R33 final `62bcb80` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R33 weakest rows | Self-improve **9.97**, Enhancement 1/2/4 + Conductor **9.96** | MiniMax music API | Jeff 02:00 — 410 not entitled |
| R33 structural #5 | **24h stale badge** on Self-improve dashboard + Settings | Hide stale behind OK text | Jeff cannot see terminal |
| ADDED 02:03 dashboard | **Ops snapshot** plain-English stale labels (>3m / >10m) | Extra raw JSON on phone | Chat-first |
| Conductor parity | **Start round** quick chip → confirm card + queue goal | Telling Jeff to run rounds manually | ADDED 04:18 |
| Music ($0) | **Nashville numbers** coach in parity eval | Paid gen | Keys Jeff has |
| Failover | `WEBCHAT_HANDBACK_TAG=r34` ×2 isolated | Prod mutation | Zero lost context |

## R34 build focus (lowest R33 scores first)

1. **Self-improve (9.97):** Stale (>24h) prefix on `dashboard_plain` Self-improve row + `log_stale_24h` in API.
2. **Dashboard (02:03):** Ops snapshot stale wording; detailed RESULT table for live ops pipeline.
3. **Conductor parity (9.96):** `parse_ready_round` for Start round chip → draft job confirm.
4. **Music (9.99):** Nashville numbers coach ($0).
5. **Failover (TOP):** handback drill ×2 (`r34`) + ts.net ready drill.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

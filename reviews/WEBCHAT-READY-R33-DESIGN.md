# Web Bob Round 33 — design note (research-first, on R16/R32 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R32 final `e7d9f44` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R32 weakest rows | Self-improve **9.95**, iPhone **9.95**, voice/enhancement **9.96** | MiniMax music API | Jeff 02:00 — 410 not entitled |
| R32 structural #5 | **Also job log** plain row (2nd screen job last log line) + tap to card | Duplicate full job cards in grid | 18-row cap; chat-first |
| R16 structural #5 | **Focus trap** after `focus_live_job` jump (Stop button) | New modal per job | Apple HIG keyboard nav |
| ADDED 02:03 dashboard | **Self-improve** row on Jobs + Pages plain grid | Raw log paths | Plain English |
| Music ($0) | **Double-chorus** + **capo** coach in parity eval (**50/50**) | Paid gen | Keys Jeff has |
| Failover | `WEBCHAT_HANDBACK_TAG=r33` ×2 isolated | Prod mutation | Zero lost context |

## R33 build focus (lowest R32 scores first)

1. **Self-improve (9.95):** `dashboard_plain` **Self-improve** row from launchd + tick log; R33 logged in handback + RESULT.
2. **Dashboard (02:03):** **Also job log** when ≥2 live screen jobs; inherited Top/Also/More tap-through.
3. **iPhone / Enhancement 3 (9.95–9.99):** Keyboard focus on job card after dashboard jump.
4. **Music (9.98):** Double-chorus + capo parity ($0).
5. **Failover (TOP):** handback drill ×2 (`r33`) + ts.net ready drill.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

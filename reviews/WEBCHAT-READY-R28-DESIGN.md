# Web Bob Round 28 — design note (research-first, on R27 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R27 final `4b6fb34` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R27 weakest rows | Speed 9.82, Self-improve 9.86, Music 9.91 | MiniMax music API | Jeff 02:00 — 410 not entitled |
| ADDED 02:03 dashboard | `live_activity_preview` on Jobs/Models ops | Raw log filenames | Plain English on phone |
| Cheap-first routing | `try_exact_reply` + wider status phrases | Fake model answers | Honest echo for explicit asks |
| ALIGNMENT handback | `WEBCHAT_HANDBACK_TAG=r28` ×2 isolated | Prod mutation | Zero lost context both ways |
| Council R27 | Ship after gates + independent grader | Self-grade only | Fail-closed |

## R28 build focus (lowest R27 scores first)

1. **Speed (9.82):** `try_exact_reply` for `Reply with exactly: …` (ready drill path); cheap status for `update?` / `how's it going?`.
2. **Self-improve (9.86):** `score_push_plain` in API + Settings (nightly focus on weakest scorecard row).
3. **Music (9.91):** **Authentic cadence (V→I)** on $0 progression scan; parity +3 cases.
4. **Dashboard / conductor (9.94):** `live_activity_preview` in enrich pipeline + **Live activity** ops row (Models + Jobs).
5. **Failover proof:** handback drill ×2 + ts.net ready drill; Bob parity **40/40**.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

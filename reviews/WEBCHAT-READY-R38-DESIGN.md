# Web Bob Round 38 — design note (research-first, on R36/R37 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R36 `848a40a` / R37 design (unshipped) · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| ADDED 02:03 dashboard | `gap_to_nine` on Jobs **Weakest score** row (matches Settings) | Duplicate score tables | One enrich path in `live_dashboard.py` |
| R36 scorecard | Failover ×2 isolated first | Prod handback mutation | Zero lost context |
| Jeff 02:00 music | Half-cadence coach ($0) | MiniMax music API | 410 not entitled |
| web.dev contrast | Distinct `.call-you` accent in live call transcript | Same color for both speakers | Voice was tied lowest with self-improve |
| Apple HIG | 44pt targets unchanged | Pop-over tabs | R36 iPhone tab bar already shipped |

## R38 build focus (lowest R36 scores first)

1. **Failover (TOP):** handback drill ×2 (`r38-1`, `r38-2`), `prod_unchanged: true`, reverse + `events_ok`.
2. **Self-improve (9.98):** Jobs dashboard weakest row shows **gap to 9** + headroom to 10.
3. **Voice (9.98):** Live call transcript distinguishes Jeff vs Web Bob lines.
4. **Music (9.99):** Half-cadence songwriting coach ($0).
5. **Dashboard (02:03):** Document full pipeline in RESULT; re-run `e2e_live.py --isolated`.

## Council

Gemini + MiniMax + Claude via `council.py`; vote on disagreements; no Grok.

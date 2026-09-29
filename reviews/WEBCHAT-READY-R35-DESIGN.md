# Web Bob Round 35 — design note (research-first, on R34)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R34 final `e3b8aa6` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R34 structural #5 + council R34 | **Unknown** ops snapshot when `generated_at` missing/unreadable | Omit Ops snapshot row | Jeff cannot see terminal; council required Unknown not healthy |
| R34 weakest rows | **iPhone design 9.96**, Enhancement 1/4 **9.96** | MiniMax music API | Jeff 02:00 — 410 not entitled |
| ADDED 02:03 dashboard | Expand RESULT **detailed live dashboard** table for unknown + stale contract | Raw JSON on phone | Chat-first |
| Music ($0) | **Cadence** coach in parity eval (logic already in `music_notebook.py`) | Paid gen | Keys Jeff has |
| Failover TOP | `WEBCHAT_HANDBACK_TAG=r35` ×2 isolated | Prod mutation | Zero lost context |

## R35 build focus (lowest R34 scores first)

1. **Dashboard (02:03):** Ops snapshot **Unknown** row + `ops_snapshot_freshness_unknown` on public bundle; Models tab matches Jobs plain English.
2. **iPhone design (9.96):** Slightly higher chat contrast behind modals (readability).
3. **Music (9.99):** Cadence coach parity case ($0).
4. **Failover (TOP):** handback drill ×2 (`r35`) + ts.net ready drill.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

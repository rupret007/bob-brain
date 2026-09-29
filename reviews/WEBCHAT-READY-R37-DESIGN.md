# Web Bob Round 37 — design note (research-first, on R36/R15 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R36 `848a40a` / R15 `397eefb` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| ADDED 02:03 dashboard | `scores_weakest_focus` + headroom on Jobs **Weakest score** row | Builder self-grading only | Independent focus from latest READY RESULT |
| R27/R26 council | `plain_status` names focus without `loop_ready` gate | Hiding weakest area when launchd off | Jeff needs next fix target on phone |
| R36 failover TOP | `WEBCHAT_HANDBACK_TAG=r37` ×2 isolated | Prod ledger mutation | Zero lost context |
| Jeff 02:00 music | Existing coaches ($0) | MiniMax music API | 410 not entitled |
| web.dev contrast | Call transcript weight + accent mix | Faded assistant call text | Voice was lowest R36 row |

## R37 build focus (lowest R36 scores first)

1. **Failover (TOP):** handback drill ×2 (`r37-1`, `r37-2`), `prod_unchanged: true`, reverse + `events_ok`.
2. **Self-improve (9.98):** `scores_weakest_focus` in Settings + Jobs dashboard headroom (`· X to 10`).
3. **Voice (9.98):** Full-contrast live call transcript lines.
4. **Dashboard (02:03):** Document pipeline in RESULT; public API exposes `scores_weakest_focus`.
5. **Parity:** Re-run 25-task eval; Web Bob must beat Bob.

## Council

Gemini + MiniMax + Claude via `council.py`; vote on disagreements; no Grok.

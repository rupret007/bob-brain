# Web Bob Round 17 — design note (research-first, on R38 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R38 `faec74b` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [LangGraph handoff patterns](https://langchain-ai.github.io/langgraph/concepts/multi_agent/) | Isolated drill fixtures + append-only handback ledger | Shared mutable chat state across agents | Zero lost context; `prod_unchanged` gate |
| [web.dev readable typography](https://web.dev/articles/accessible-tap-targets) | Italic/emphasis in assistant markdown; 44pt chips unchanged | Raw `**` in Jobs tab | Enhancement 1 — mobile formatting |
| R38 scorecard (lowest **9.98**) | Wire `parse_ready_round` in server submit path; chip uses READY phrase | Generic `start a job: ready round` string | Conductor parity + Enhancement 2 |
| Jeff 02:00 music | Plagal (amen) IV→I coach ($0) | MiniMax music API (410) | Music row without spend |
| ADDED 02:03 dashboard | Full pipeline table in RESULT; inherit `gap_to_nine` + headroom | Second score writer | Single `enrich_live_ops_bundle` path |
| ALIGNMENT-DESIGN.md | `events.jsonl` + BOB-CATCHUP on wake | Bob polling | Bob usage cap to ~10/2 |

## R17 build focus (lowest R38 scores first)

1. **Failover (TOP):** handback drill ×2 (`r17-1`, `r17-2`), `prod_unchanged: true`, reverse + `events_ok`.
2. **Conductor parity (9.98):** `parse_ready_round` → default READY goal confirm card (same as Start round chip).
3. **Enhancement 1 (9.98):** `_italic_` / `*em*` in `renderMarkdown` for assistant bubbles.
4. **Enhancement 2 (9.98):** ready-round + do-more paths tested end-to-end in `test_webchat.py`.
5. **Music (9.99):** plagal cadence coach ($0).
6. **Dashboard (02:03):** document full live ops pipeline in RESULT; `e2e_live.py --isolated`.

## Council

Gemini + MiniMax + Claude via `conductor/services/council.py`; disagreements resolved by council vote; no Grok.

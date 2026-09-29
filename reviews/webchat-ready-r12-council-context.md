# Round 12 council context (refresh on R14 baseline)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R14 final `4c209df` · **No Grok.**

## R12 delta (this commit)

1. **`conductor/state/ledger.py`:** `compact_dropped_drill_open_asks()` removes dropped drill noise from `open_asks` (P0 03:17 — drills must not pollute Jeff status/catch-up).
2. **`conductor/webchat/app.py`:** compact on webchat startup after purge.
3. **`conductor/webchat/music_notebook.py`:** Supertonic (ii) on $0 progression scan (no MiniMax music API).
4. **Tests:** `test_compact_dropped_drill_open_asks`, supertonic assertions on progression scan.

## Gates (ship draft after PASS)

| Gate | Command / tag |
|------|----------------|
| Unit | `python3 conductor/webchat/test_webchat.py` — 107 OK |
| Failover | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services | `python3 conductor/services/test_services.py` — 52 OK |
| Bob parity | 32/32 `bob_parity_eval.py` — Web Bob beats Bob |
| ts.net drill | `live_ready_drill.py` — p50, merge refusal |
| Handback ×2 | `WEBCHAT_HANDBACK_TAG=r12` isolated, `prod_unchanged: true` |
| Live dashboard | `build_live_ops` + `ops_snapshot_age_seconds`, running_jobs last 3 log lines, scores table |

## Council vote

Gemini + MiniMax + Claude (short); synthesizer breaks ties. Disagreement: hold until evidence bundle + this RESULT.

## Lowest scores to lift (R12 focus)

Self-improve loop, run-jobs-from-chat, live dashboard `scores_weakest`, voice/mobile contrast, music ($0 only).

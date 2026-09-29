# Round 26 council context (diff summary)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R25 `9d4d27f`

## Changes

1. **`conductor/webchat/app.py`:** `self_improve_status()` adds `scores_weakest_focus` via `live_dashboard._scores_table()` / `_scores_weakest()`; loop-ready `plain_status` mentions next focus.
2. **`conductor/webchat/static/app.js`:** Settings self-improve details show score focus; Jobs ops job rows append `last_commit.message`.
3. **`conductor/webchat/static/style.css`:** Voice transcript contrast; assistant `md-link` styling.
4. **`conductor/webchat/music_notebook.py`:** Subdominant (IV) line on progression scan ($0).
5. **`conductor/webchat/live_handback_drill.py`:** Up to 3 attempts on `assert_prod_unchanged` with 1.5s pause (handback/STATE race).
6. **Tests:** `test_self_improve_exposes_scores_weakest_focus`, subdominant progression assertions, `bob_parity_eval` subdominant case.

## Gates (required before ship draft)

- `python3 conductor/webchat/test_webchat.py`
- `python3 conductor/webchat/test_failover.py`
- `python3 conductor/services/test_services.py`
- `python3 conductor/webchat/bob_parity_eval.py` — must beat Bob (31/31)
- `WEBCHAT_HANDBACK_TAG=r26 python3 conductor/webchat/live_handback_drill.py` ×1 run (2 rounds inside)
- `python3 conductor/webchat/live_ready_drill.py`
- Restart webchat on 8787 after deploy

## Priority disagreement resolution

If council ranks music vs self-improve vs dashboard differently: **vote** — self-improve focus (#1), voice/mobile (#2), dashboard commit message (#3), music IV (#4).

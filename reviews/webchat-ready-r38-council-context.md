# Round 38 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R36 RESULT `848a40a` · **No Grok.**

## Priority (lowest measured R36 scores)

1. Failover handback ×2 (`r38-1`, `r38-2`) — isolated, `prod_unchanged: true`.
2. Self-improve: `gap_to_nine` on Jobs `dashboard_plain` weakest row (with headroom).
3. Voice: `.call-transcript .call-you` accent in `static/style.css`.
4. Music: half-cadence coach in `music_notebook.py` ($0).
5. `e2e_live.py --isolated` + detailed live dashboard section in RESULT.

## Code touch list

1. `conductor/services/live_dashboard.py` — gap_to_nine on weakest row.
2. `conductor/webchat/static/style.css` — call transcript you/bob contrast.
3. `conductor/webchat/music_notebook.py` — half cadence coach.
4. Tests: `test_dashboard_plain_weakest_gap_to_nine`, half-cadence music case.

## Gates

`test_webchat.py`, `test_failover.py`, `test_services.py` (66), `bob_parity_eval.py`, `live_ready_drill.py`, `WEBCHAT_HANDBACK_TAG=r38 live_handback_drill.py` ×2, `e2e_live.py --isolated`, quiet hours JS, iPhone `iphone-r38` screenshots, council, safe restart `:8787`.

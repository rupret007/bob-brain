# Round 37 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R36 RESULT `848a40a` · **No Grok.**

## Priority (lowest measured R36 scores)

1. Failover handback ×2 (`r37-1`, `r37-2`) — isolated, `prod_unchanged: true`.
2. Self-improve: `scores_weakest_focus` + gap/headroom on Settings and Jobs `dashboard_plain` weakest row.
3. Voice: call transcript contrast in `static/style.css`.
4. Detailed live dashboard section in RESULT (ADDED 02:03).

## Code touch list

1. `conductor/services/live_dashboard.py` — `_scores_weakest_focus`, headroom on weakest row, public field.
2. `conductor/webchat/app.py` — self-improve focus + panel merge before enrich.
3. `conductor/webchat/static/app.js` — Settings/Models focus lines.
4. Tests: `test_self_improve_exposes_scores_weakest_focus`, `test_dashboard_plain_weakest_headroom`.

## Gates

`test_webchat.py`, `test_failover.py`, `test_services.py`, `bob_parity_eval.py`, `live_ready_drill.py`, `WEBCHAT_HANDBACK_TAG=r37 live_handback_drill.py` ×2, `e2e_live.py --isolated`, quiet hours JS, iPhone `iphone-r37` screenshots, council, safe restart `:8787`.

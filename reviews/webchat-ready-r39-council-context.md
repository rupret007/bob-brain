# Round 39 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R37 RESULT · **No Grok.**

## Priority (lowest measured R37 scores)

1. Failover handback ×2 (`r39-1`, `r39-2`) — isolated, `prod_unchanged: true`, `prod_race_retries` if autopilot writes.
2. Enhancement 2 — run jobs from chat (`parse_do_more`, queue confirm path).
3. Conductor parity — act-as-conductor RULES, council chip, drills on server.
4. Voice — `.call-transcript .call-you` vs `.call-bob` contrast in `static/style.css`.
5. `e2e_live.py --isolated` + detailed live dashboard in RESULT.

## Code touch list

1. `conductor/webchat/live_handback_drill.py` — retry on production fingerprint race.
2. `conductor/webchat/static/style.css` — call transcript contrast.
3. `conductor/services/live_dashboard.py` — inherited `gap_to_nine` on weakest row.

## Gates

`test_webchat.py`, `test_failover.py`, `test_services.py` (66), `bob_parity_eval.py`, `live_ready_drill.py`, `BOB_WEBCHAT_DRILLS=1` + `WEBCHAT_HANDBACK_TAG=r39 live_handback_drill.py`, `e2e_live.py --isolated`, quiet hours JS, iPhone `iphone-r39` screenshots, council, safe restart `:8787`.

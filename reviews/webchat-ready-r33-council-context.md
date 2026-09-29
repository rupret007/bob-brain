# Round 33 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R32 `e7d9f44` · **No Grok.**

## Proposed deltas

1. **Dashboard:** `dashboard_plain` adds **Also job log** (2nd job last log line, `focus_live_job` index 1) and **Self-improve** plain row from tick/plist/log probe.
2. **Jobs UI:** After dashboard tap-through, focus first action button on target live job card.
3. **Music:** `music double-chorus coach` + `music capo coach` in `bob_parity_eval.py` (**50/50**).
4. **Failover:** `WEBCHAT_HANDBACK_TAG=r33` handback drill ×2, `prod_unchanged: true`.

## Gates (must PASS before ship draft)

- `python3 conductor/webchat/test_webchat.py`
- `python3 conductor/webchat/test_failover.py`
- `python3 conductor/services/test_services.py`
- `python3 conductor/webchat/bob_parity_eval.py` (50/50)
- `python3 conductor/webchat/live_ready_drill.py` (ts.net)
- `WEBCHAT_HANDBACK_TAG=r33 python3 conductor/webchat/live_handback_drill.py` (`rounds: 2`)
- `node conductor/webchat/test_quiet_hours_js.mjs`
- `WEBCHAT_IPHONE_EVIDENCE=iphone-r33 node conductor/webchat/capture_iphone.cjs`

**Question for council:** Round 33 Web Bob: Also job log + Self-improve dashboard rows, job-card focus after jump, double-chorus/capo parity, handback r33×2. Ship draft after gates or hold? Priority if disagree: failover #1, dashboard #2, self-improve #3, focus trap #4, music #5.

# Round 31 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R30 `72e490b` · **No Grok.**

## Proposed deltas

1. **Dashboard:** `enrich_live_ops_bundle` builds `dashboard_plain` *after* `attach_scheduler_queue` so **Scheduler queue** shows on Jobs + Pages; add **Ops snapshot** row to plain grid.
2. **Enhancement 2:** Action confirm cards show plain-English goal before approve.
3. **Voice:** Settings toggle `speak-replies-auto` + shared `speakAssistantContent`; quiet hours respected.
4. **Music:** `music bridge coach` in `bob_parity_eval.py` (43 cases).
5. **Failover:** `WEBCHAT_HANDBACK_TAG=r31` handback drill ×2, `prod_unchanged: true`.

## Gates (must PASS before ship draft)

- `python3 conductor/webchat/test_webchat.py`
- `python3 conductor/webchat/test_failover.py`
- `python3 conductor/services/test_services.py` (includes new dashboard tests)
- `python3 conductor/webchat/bob_parity_eval.py` (43/43)
- `python3 conductor/webchat/live_ready_drill.py` (ts.net)
- `WEBCHAT_HANDBACK_TAG=r31 python3 conductor/webchat/live_handback_drill.py` (twice / `rounds: 2`)
- `node conductor/webchat/test_quiet_hours_js.mjs`
- `WEBCHAT_IPHONE_EVIDENCE=iphone-r31 node conductor/webchat/capture_iphone.cjs`

**Question for council:** Round 31 Web Bob: dashboard queue plain fix, voice auto read-aloud toggle, job goal on confirm cards, bridge music parity, handback r31×2. Ship draft after gates or hold? Priority if disagree: failover #1, dashboard #2, enhancement 2 #3, voice #4, music #5.

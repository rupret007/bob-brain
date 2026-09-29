# Round 30 council context (for `council.py`)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R29 `5c2b964` · **No Grok.**

## Proposed deltas

1. **Dashboard:** `dashboard_plain` adds deploy version, safe restart, replies in flight, scores updated, stalled jobs, last commit, recent logs (3 lines); `panel()` re-enriches `live_ops` after in-flight/deploy known.
2. **Mobile formatting:** blockquote markdown, contrast fix; Jobs tab `dashboard_plain` (no chat chrome).
3. **Self-improve:** `install_one_liner` + Settings `chat_queue_hint`.
4. **Conductor:** autopilot status when `in_flight_replies > 0`.
5. **Music:** explicit `meter scan` phrase; parity **42/42**.

## Required gates before ship draft

- `python3 conductor/webchat/test_webchat.py` (115+)
- `python3 conductor/webchat/test_failover.py` (23)
- `python3 conductor/services/test_services.py` (54+)
- `python3 conductor/webchat/bob_parity_eval.py` (**42/42**)
- `WEBCHAT_HANDBACK_TAG=r30 python3 conductor/webchat/live_handback_drill.py` (`rounds: 2`, `prod_unchanged: true`)
- `python3 conductor/webchat/live_ready_drill.py` (ts.net p50)
- `WEBCHAT_IPHONE_EVIDENCE=iphone-r30 node conductor/webchat/capture_iphone.cjs` (≥0.75)
- `node conductor/webchat/test_quiet_hours_js.mjs`
- Restart `127.0.0.1:8787` via `bash conductor/webchat/start.sh`

**Question for council:** Round 30 Web Bob: detailed dashboard_plain, chat live strip, self-improve hints, conductor in-flight status, meter scan. Ship draft after gates or hold? Priority if disagree: dashboard #1, mobile #2, self-improve #3, conductor #4, music #5.

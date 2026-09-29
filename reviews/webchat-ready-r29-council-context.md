# Round 29 council context (for `council.py`)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R28 `38e6aa4` · **No Grok.**

## Diff summary (R29)

1. **Enhancement 2:** Start job chip; queued message includes goal snippet; action cards unchanged (position + View in Jobs).
2. **Self-improve:** `chat_queue_hint` when weakest row is job/conductor-related (or default queue hint).
3. **Live dashboard:** `_build_dashboard_plain()` → `dashboard_plain[]`; Jobs tab renders grid + `live_activity_preview` line; Pages via `public_live_ops`.
4. **Music:** Half cadence (ends on V) on progression scan; bob parity **41/41**.
5. **Tests:** 112 webchat + 23 failover + 53 services.

## Gates (must PASS before ship draft)

- `python3 conductor/webchat/test_webchat.py` — 112 OK
- `python3 conductor/webchat/test_failover.py` — 23 OK
- `python3 conductor/services/test_services.py` — 53 OK
- `python3 conductor/webchat/bob_parity_eval.py` — 41/41
- `WEBCHAT_HANDBACK_TAG=r29 python3 conductor/webchat/live_handback_drill.py` — `rounds: 2`, `prod_unchanged: true`
- `python3 conductor/webchat/live_ready_drill.py` — ts.net p50 recorded
- `WEBCHAT_IPHONE_EVIDENCE=iphone-r29 node conductor/webchat/capture_iphone.cjs`
- `conductor/reviews/WEBCHAT-READY-R29-RESULT.md` with scorecard + SHAs

**Question for council:** Round 29 Web Bob: dashboard_plain, Start job chip, chat_queue_hint, half cadence. Ship draft after gates or hold? Priority if disagree: dashboard #1, enhancement 2 #2, self-improve #3, music #4.

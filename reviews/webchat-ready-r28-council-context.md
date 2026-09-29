# Round 28 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R27 `4b6fb34` · **No Grok.**

## Delta

1. **Speed:** `try_exact_reply` short-circuit; ledger cheap status for `update?` / `how's it going?`.
2. **Self-improve:** `score_push_plain` in `self_improve_status()` + Settings.
3. **Music ($0):** Authentic cadence (V→I) on progression scan.
4. **Live dashboard:** `live_activity_preview` + **Live activity** row on Jobs/Models ops detail.
5. **Proof:** 111+ webchat tests, handback `r28` ×2, parity **40/40**, ts.net drill, iphone-r28 screenshots.

## Gates

- `python3 conductor/webchat/test_webchat.py`
- `python3 conductor/webchat/test_failover.py`
- `python3 conductor/services/test_services.py`
- `python3 conductor/webchat/bob_parity_eval.py`
- `WEBCHAT_HANDBACK_TAG=r28 python3 conductor/webchat/live_handback_drill.py`
- `python3 conductor/webchat/live_ready_drill.py`
- Restart `127.0.0.1:8787` after deploy

## Question

Round 28 Web Bob on R27 baseline: exact-reply speed, live activity dashboard row, authentic cadence, score_push_plain. Ship draft after gates or hold? Priority if disagree: speed #1, dashboard #2, self-improve #3, music #4.

# Round 27 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R17 `db564cf` · **No Grok.**

## Delta

1. **Self-improve:** weakest-score focus in `plain_status` without requiring `loop_ready`; Setup gap-to-9 display.
2. **Music ($0):** Tonic (I) on progression scan.
3. **Live dashboard:** Deploy version + Safe restart rows on Jobs/Models ops detail (from panel).
4. **Proof:** 108+ webchat tests, handback `r27` ×2, parity 35/35, ts.net drill, iphone-r27 screenshots.

## Gates

- `python3 conductor/webchat/test_webchat.py`
- `python3 conductor/webchat/test_failover.py`
- `python3 conductor/services/test_services.py`
- `python3 conductor/webchat/bob_parity_eval.py`
- `WEBCHAT_HANDBACK_TAG=r27 python3 conductor/webchat/live_handback_drill.py`
- `python3 conductor/webchat/live_ready_drill.py`
- Restart `127.0.0.1:8787` after deploy

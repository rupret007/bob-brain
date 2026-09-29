# Round 32 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R31 `78a4ab1` · **No Grok.**

## Proposed deltas

1. **Dashboard:** `dashboard_plain` includes **Bob catch-up** row; overflow shows **More fields (+N)** with `dashboard_plain_omitted` on public ops bundle.
2. **Jobs UI:** Render up to **18** plain rows (was 10); highlight overflow row.
3. **iPhone:** `body.modal-open` dims chat bubbles behind dialogs (contrast fix).
4. **Voice:** Settings **read-aloud speed** select; `speakRateValue()` for auto read-aloud.
5. **Music:** `music intro coach` + `music outro coach` in `bob_parity_eval.py` (**45/45**).
6. **Failover:** `WEBCHAT_HANDBACK_TAG=r32` handback drill ×2, `prod_unchanged: true`.

## Gates (must PASS before ship draft)

- `python3 conductor/webchat/test_webchat.py`
- `python3 conductor/webchat/test_failover.py`
- `python3 conductor/services/test_services.py`
- `python3 conductor/webchat/bob_parity_eval.py` (45/45)
- `python3 conductor/webchat/live_ready_drill.py` (ts.net)
- `WEBCHAT_HANDBACK_TAG=r32 python3 conductor/webchat/live_handback_drill.py` (`rounds: 2`)
- `node conductor/webchat/test_quiet_hours_js.mjs`
- `WEBCHAT_IPHONE_EVIDENCE=iphone-r32 node conductor/webchat/capture_iphone.cjs`

**Question for council:** Round 32 Web Bob: dashboard overflow + catch-up plain row, voice speed, modal contrast, intro/outro music parity, handback r32×2. Ship draft after gates or hold? Priority if disagree: failover #1, dashboard #2, iPhone contrast #3, voice #4, music #5.

# Round 36 council context

**Branch:** `draft/webchat-failover-20260927` · **No Grok.**

## Changes

1. **`job_queue.py`:** `parse_do_more`, natural `Ask the council to …` parse.
2. **`live_dashboard.py`:** `enrich_live_ops_bundle`, `dashboard_plain[]`, ops snapshot freshness, public bundle fields.
3. **`ops_panel.py` / `app.py`:** Enrich with repo root for catch-up + self-improve rows.
4. **`static/`:** `#jobs-dashboard-plain` grid, focus job jump, mic/call contrast.
5. **`providers.py`:** Conductor-when-away RULES; `overlay_pins` for in-flight drill overlay.

## Gates

- `python3 conductor/webchat/test_webchat.py` (89)
- `python3 conductor/webchat/test_failover.py` (23)
- `python3 conductor/services/test_services.py` (33)
- `bob_parity_eval.py` 25/25
- `WEBCHAT_HANDBACK_TAG=r36` handback ×2
- `live_ready_drill.py` + e2e if available
- Restart `127.0.0.1:8787`

Question: Ship draft round 36 after gates? Priority if disagree: failover → dashboard_plain → conductor RULES → voice contrast.

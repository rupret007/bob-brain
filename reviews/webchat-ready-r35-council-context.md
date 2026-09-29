# Council context — Web Bob Round 35

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R34 `e3b8aa6`

## Build focus

1. **Ops snapshot Unknown:** `live_dashboard._ops_snapshot_plain_text` always emits Ops snapshot; missing `generated_at` → `Unknown — cannot verify freshness`; bad ISO → `Unknown — timestamp unreadable`; flag `ops_snapshot_freshness_unknown` on bundle + `public_live_ops()`.
2. **iPhone:** modal-open chat dim less aggressive (contrast).
3. **Music:** cadence coach in `bob_parity_eval.py` ($0).
4. **Failover:** `WEBCHAT_HANDBACK_TAG=r35` ×2 isolated.

## Gates

- `test_webchat.py`, `test_failover.py`, `test_services.py` PASS
- parity **53/53** (cadence case)
- handback ×2 `prod_unchanged: true`
- `live_ready_drill.py` ts.net
- `iphone-r35` screenshots ≥0.75

**Question for council:** Round 35 Web Bob: ops snapshot Unknown badge, cadence coach, handback r35×2, modal contrast. Ship draft after gates or hold? Priority if disagree: failover #1, dashboard #2, iPhone contrast #3, music #4.

# Round 34 council context (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R33 `62bcb80`

## Delta

1. **Self-improve stale badge:** `live_dashboard._self_improve_plain_line` prefixes `Stale (>Nh since log)` when log mtime >24h; `self_improve_log_stale_24h` on bundle; Jobs UI highlights Self-improve + Ops snapshot stale rows.
2. **Ops snapshot:** plain labels `May be stale` (>180s) / `Stale` (>600s).
3. **Conductor:** `parse_ready_round` maps Start round chip to READY phone round job goal + confirm card.
4. **Music:** Nashville numbers coach ($0) + parity eval cases.
5. **Failover:** `WEBCHAT_HANDBACK_TAG=r34` ×2 isolated.

## Gates

- `test_webchat.py`, `test_failover.py`, `test_services.py` PASS
- `bob_parity_eval.py` 52/52 (Web Bob beats Bob)
- `live_handback_drill.py` ×2 `prod_unchanged: true`
- `live_ready_drill.py` ts.net path
- `iphone-r34` screenshots ≥0.75

**Question for council:** Round 34 Web Bob: self-improve 24h stale badge, ops snapshot stale labels, Start round conductor chip, Nashville coach, handback r34×2. Ship draft after gates or hold? Priority if disagree: failover #1, dashboard #2, self-improve stale #3, conductor chip #4, music #5.

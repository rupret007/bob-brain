# Council context — Web Bob Round 22 (on R15 baseline)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R15 final `397eefb`

## Diff summary (this round)

1. **iPhone-first (P0):** `quick-chips-row` + `toggle-chips` (collapsed default ≤430px); Grok-style composer (mic + call-in-pill, placeholder “Ask Bob the Bot”); typing indicator (avatar + dots); `body.modal-open` dim behind dialogs.
2. **`app.py`:** Job/council confirm `action_card.goal`; self-improve `wait_for_tick` includes schedule in `next_action_plain`.
3. **`app.js`:** Chips persistence, modal toggle, action-card goal rendering.
4. **Tests:** `test_chat_index_includes_toggle_chips`, job goal on confirm card, schedule in wait_for_tick plain text.

## Gates (must PASS before ship draft RESULT)

- `python3 conductor/webchat/test_webchat.py` (96+)
- `python3 conductor/webchat/test_failover.py` (23)
- `python3 conductor/services/test_services.py` (66)
- `python3 conductor/webchat/bob_parity_eval.py` 25/25
- `python3 conductor/webchat/live_ready_drill.py` ts.net p50
- `WEBCHAT_HANDBACK_TAG=r22` `live_handback_drill.py` ×2 `prod_unchanged: true` (server `BOB_WEBCHAT_DRILLS=1`)
- `python3 conductor/webchat/e2e_live.py --output webchat/evidence/e2e-r22.json`
- `WEBCHAT_IPHONE_EVIDENCE=iphone-r22` `capture_iphone.cjs` layout ≥0.75
- `node conductor/webchat/test_quiet_hours_js.mjs`

**Hard rules:** drafts only; no merge; no Grok; no MiniMax music API.

**Ask council:** Review iPhone screenshots in `webchat/evidence/iphone-r22/` and diff; ship draft RESULT after gates?

# Council context — Web Bob Round 15 (on R21 baseline)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R21 final `b1f827a`

## Diff summary (this round)

1. **`index.html`:** Models **Refresh** button (`#refresh-dashboard`); Settings **Copy install** + `self-improve-next`; Help lists Models refresh + Settings.
2. **`app.py`:** `self_improve_status()` adds `next_action` + `next_action_plain` (install_launchd | loop_ready | …).
3. **`app.js`:** Settings shows `next_action_plain`.
4. **`style.css`:** Slimmer header ≤430px; voice/call transcript full contrast.
5. **`music_notebook.py`:** deceptive cadence V→vi coach ($0).
6. **Tests:** `test_self_improve_next_action_install_launchd`, deceptive cadence in music coach test.

## Priorities if council disagrees

1. Bidirectional handback ×2 with `prod_unchanged: true`
2. Bob parity 25/25 beat Bob
3. Self-improve clarity (#1 score gap)
4. Live dashboard Refresh + focus rows
5. Voice contrast

**Hard rules:** drafts only; no merge; no Grok; no MiniMax music API.

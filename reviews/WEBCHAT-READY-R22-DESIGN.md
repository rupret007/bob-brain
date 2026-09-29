# Web Bob Round 22 — design note (research-first)

**Baseline:** R15 measured scores (`WEBCHAT-READY-R15-RESULT.md`, SHA `397eefb`).

## Research (what exists today)

- **Jeff device:** iOS Safari + Tailscale ts.net PWA; Grok Bot app as visual north star (`grokbot-ref-chatbar-0346.png`, ADDED 03:47).
- **This repo:** Bottom tab bar (Chat/Jobs/Songs/Models/Settings), `live_dashboard.py` → Jobs/Models panels, isolated handback drills, 25-task Bob parity eval.
- **Patterns reviewed:** Apple HIG tab bars + 44pt targets; ChatGPT/Claude iOS chat-first layouts; collapsed accessory rows on narrow viewports; typing indicators with agent avatar (common in iMessage/assistant apps).
- **Council prior art:** R15/R21 ship gates; R19/R20 council asked for `toggle-chips` + modal dim — partially regressed in R15 slim header pass.

## Borrow

- **Grok-style composer:** Mic inside pill, waveform call control at pill edge, placeholder “Ask Bob the Bot”, send as compact circle (Enter on iOS).
- **Collapsed quick chips** on ≤430px with persisted `bob.chipsCollapsed` — frees vertical space for ≥75% chat (`capture_iphone.cjs`).
- **Typing row** (avatar + animated dots) instead of dashed “One moment…” bubble text.
- **Modal dim** (`body.modal-open`) so conversation picker doesn’t fight sheet contrast.
- **Job/council confirm cards** show explicit `goal` string bound to proposal id (Enhancement 2 gap).
- **Self-improve:** surface `schedule_hint` in “Next:” when waiting on launchd tick (lowest score area).
- **Live dashboard:** keep R15 `enrich_live_ops_bundle` contract; Jobs Refresh unchanged.

## Reject

- MiniMax music API / new signups (Jeff 02:00).
- Grok as worker; merging or force-push.
- Status panels above `#messages` (Jeff 02:18).
- Passive dashboard refresh on every `GET /api/panel` (R15 architecture).
- Re-adding raw STATUS.md dumps in Chat tab.

## Why (lowest R15 scores first)

1. **Self-improve 9.50** → clearer next tick + schedule on Settings.
2. **Enhancement 2 — run jobs 9.68** → visible goal on approve cards + tests.
3. **Speed 9.72** → no server change; verify ready drill + avoid extra restarts.
4. **Conductor / voice 9.72** → typing indicator + composer layout (call in pill) + transcript contrast retained.
5. **iPhone design 9.92** → chips collapse + Grok composer + typing row; screenshot council review.

**Sources:** `WEBCHAT-READY.md` ADDED 02:11–02:30, 03:47; `WEBCHAT-READY-R15-RESULT.md`; Apple HIG; `worktrees/webbob-e2e-0927` (typing/chips patterns, not shipped wholesale).

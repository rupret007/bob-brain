# Web Bob iPhone-first design — Round 9 research note

**Date:** 2026-09-27 · **Primary device:** iPhone Safari / Add to Home Screen  
**Goal:** Chat-first UI ≥75% viewport height; ops in tabs; plain English; Grok Bot iOS feel, improved.

## Research pass (borrow / reject / why)

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Fixed bottom tab bar (5 tabs max), icons + short labels, 44pt targets, safe-area insets | Hamburger-only nav, sheet-only “Done” for primary navigation | Jeff’s screenshots showed sheet tabs hiding chat; HIG tab bar keeps one tap to Jobs/Models without covering messages. |
| [Apple HIG — Layout](https://developer.apple.com/design/human-interface-guidelines/layout) | `100dvh`, `env(safe-area-inset-*)`, 16px min body text on inputs (no zoom-on-focus) | Status markdown dumps above conversation | Readable composer on iOS requires 16px textarea; status belongs off the chat stack. |
| ChatGPT / Claude iOS (product patterns, not code) | Full-height thread, slim header (name + status), pinned composer, subtle message motion | Showing repo file names, SHA walls, or `**bold**` literals in main chrome | Jeff uses Grok Bot iOS daily; conversation is the product; ops are secondary. |
| [PWA on iOS — web.dev](https://web.dev/learn/pwa/installation/) | `apple-mobile-web-app-capable`, manifest, standalone display | Assuming push works without user grant | We ship offline banner + retry; push is stretch (R11+). |
| Material / bottom sheets (MD3) | Bottom sheet for *secondary* detail (conversation picker dialog) | Bottom sheet as main tab switcher | Sheets obscure chat (Jeff feedback 02:30); tabs stay fixed. |
| Open-source: [assistant-ui](https://github.com/assistant-ui/assistant-ui) | Composable message list + sticky composer concept | Full React migration tonight | Stack is vanilla JS; borrow layout patterns only. |
| Open-source: [LibreChat](https://github.com/danny-avila/LibreChat) | Model badge per message (subtle meta line) | Multi-model picker in header | “Who answered” lives in message meta + Models tab. |

## R9 layout decisions (implemented)

1. **Chat default** — `#view-chat` flex-grows; `#messages` scrolls; no status panel above thread.
2. **Bottom tab bar** — Chat · Jobs · Songs · Models · Settings; always visible; blur + border top.
3. **Header** — Bob + connection line + status dot only (no BOB-STATE banner, no conversation dump in header).
4. **Jobs / Models** — Live cards from `STATE.json` + `live_ops` (not handback markdown as “running”).
5. **Typography** — System font stack, assistant bubbles with full `var(--text)` contrast (fix low-contrast behind sheets).
6. **Composer** — Pinned above tab bar; quick chips; 44pt controls; keyboard-safe `dvh`.

## Council alignment

Ranked with Gemini search + prior council votes (R6–R11): **ship fixed tab bar + chat ratio gate** (Playwright ≥0.70); defer WebAuthn passkey and web push to later rounds.

## Evidence

- Screenshots: `conductor/webchat/evidence/iphone-r9/` (390×844, 430×932)
- Metrics: `layout-metrics.json` (`messages_ratio` ≥ **0.75** at 390×844 and 430×932)

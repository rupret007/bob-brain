# Web Bob Round 10 — research-first design note

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **No Grok.**

## Research pass — what exists today

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Fixed 5-tab bar, icon + label, blur material, safe-area | Pop-up sheet as primary nav | Jeff 02:30 — sheet hid chat and cut Settings label |
| [Apple HIG — Messages (patterns)](https://developer.apple.com/design/human-interface-guidelines/messages) | Full-height thread, pinned composer, slim header, high-contrast bubbles | Raw markdown / file paths in chrome | Chat is the product on iPhone |
| ChatGPT / Claude iOS (product UX, not code) | Quick actions above composer, subtle model attribution, tap-to-copy code | Multi-panel status above thread | Matches Grok Bot iPhone feel Jeff approved |
| [assistant-ui](https://github.com/assistant-ui/assistant-ui) | Sticky composer + scrollable thread separation | React rewrite tonight | Vanilla JS stack stays |
| [LibreChat](https://github.com/danny-avila/LibreChat) | Per-message provider meta; lane health cards | Exposing branch/SHA syntax in UI | Plain English in Jobs/Models |
| Temporal / LangGraph handoff docs | Isolated drill fixture + prod fingerprint (R9) | Shared drill on prod STATE | P0 leakage (`drill-r9`, fake SHAs) |
| MiniMax music API | — | Any new music endpoints (410) | Jeff 02:00 — lyrics, sketch, Logic MCP only |
| Web push (web.dev PWA) | Offline banner + retry (shipped) | Assuming iOS push without grant | Defer push to structural backlog |

## R10 build (this round)

1. **iPhone-first polish:** Tighter header/composer chrome for ≥0.75 `#messages` ratio gate; job cards with Stop/Details actions; conductor buttons submit chat actions (not syntax dumps); Models/Songs empty states; tab label fit on 390px width.
2. **Failover both ways:** Re-run `live_handback_drill.py` ×2 runs ×2 with `WEBCHAT_HANDBACK_TAG=r10`; prod fingerprint unchanged.
3. **Lowest scores:** Self-improve `healthy` signal + clearer Settings copy; music coach rhyme/meter paths; voice long-press + keyboard dictation hint; conductor one-tap actions.
4. **Live dashboard:** Jobs tab continues `live_ops` fields (NOW line, 3 log lines, stall, SHA, roles, MiniMax cap).
5. **Council:** Gemini + MiniMax + Claude critique diff; vote on disagreements.

## Council alignment (pre-build)

Rank: **ship chat-first ratio gate + job card actions + conductor submit** before new features (WebAuthn, push). Screenshots at 390×844 and 430×932 in `evidence/iphone-r10/`.

## Sources

`WEBCHAT-READY-R9-DESIGN.md`, `ALIGNMENT-DESIGN.md`, Apple HIG tab bar & layout, Jeff `WEBCHAT-READY.md` ADDED 02:11–02:30.

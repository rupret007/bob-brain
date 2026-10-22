# Web Bob Round 7 — research-first design note (iPhone-first)

**Date:** 2026-09-27 CT · **Round:** 7 (refresh) · **No Grok**

## Research pass — what exists today

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Persistent bottom tabs, 44pt targets, labels under icons | Hamburger “More” for core flows | Jeff’s primary device is iPhone; Chat/Jobs/Songs/Models/Settings must stay one tap away |
| ChatGPT / Claude iOS (chat-first assistants) | Full-height transcript, slim header, composer pinned above keyboard, extras off the chat surface | Status markdown dumps above messages | Matches Jeff’s Grok Bot reference app; conversation is the product |
| [Material 3 navigation bar](https://m3.material.io/components/navigation-bar) | Blurred bar, active state tint, 3–5 destinations | FAB clutter on every screen | We use five tabs max; blur + accent on active tab |
| [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) | Checkpointed handoff files | Remote orchestrator | `conductor/handback/` + `STATE.json` + `events.jsonl` already give zero-loss takeover on one mini |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | Read handoff payload before acting | Autonomous sends | Draft-only + confirm cards in chat |
| ALIGNMENT-DESIGN (R9+) | `events.jsonl` + SSE in Web Bob | Bob polling | Bob wakes on catch-up; Web Bob stays live |

## R7 iPhone design choices (this build)

1. **Chat ≥75% viewport** — unchanged layout metrics gate (`messages_ratio ≥ 0.7`); assistant bubbles get surface + border for contrast (fixes faded text behind sheets).
2. **Jobs tab** — scores moved to **Models**; plain-English job cards; empty state when nothing on screen; no raw filenames in commit line.
3. **Status chip** — sends `status` (cheap `STATE.json` path), not long BOB-STATE boilerplate titles.
4. **Settings** — grouped help + “What’s new” from latest `WEBCHAT-READY-R*-RESULT.md`.
5. **Trust** — `reply_guard` blocks hollow “checking… one moment” replies; drill noise filtered from open asks; handback drill restores `STATE.json` + handback.

## Council tie-break (preview)

Prefer scores on Models tab (Gemini/MiniMax align); Claude short: keep one-line NOW on Jobs — **vote: NOW on Jobs, scores on Models**.

## Sources cited

Apple HIG Tab Bars; Material 3 Navigation Bar; LangGraph persistence docs; OpenAI Agents handoffs; `conductor/reviews/ALIGNMENT-DESIGN.md`.

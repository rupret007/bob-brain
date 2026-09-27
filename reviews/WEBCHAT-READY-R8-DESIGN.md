# Web Bob Round 8 — research-first design note (iPhone-first refresh)

**Date:** 2026-09-27 CT · **Round:** 8 (refresh on R11 base) · **No Grok**

## Research pass — what exists today

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | SF-style stroke icons, 44pt targets, persistent five tabs | Emoji tab glyphs, pop-over “More” for core flows | Jeff’s primary device is iPhone; Chat/Jobs/Songs/Models/Settings stay one tap away |
| ChatGPT / Claude iOS | Chat ≥75% viewport, slim header, composer pinned, offline banner | Status markdown above the transcript | Matches Grok Bot reference; conversation is the product |
| [Material 3 navigation bar](https://m3.material.io/components/navigation-bar) | Blur + active tint on bottom bar | Cluttered FABs | Five destinations max; subtle motion on tab switch |
| [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) | Overlay fixture + handback ledger | Remote orchestrator | Isolated `drill-fixtures/` + overlay API proves zero-loss without touching prod handback |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | Read BOB-STATE before act; cheap state path on overlay | Autonomous sends | `try_bob_state_running_line` for drill takeover; draft-only cards in chat |
| Suno/Udio / MiniMax music API | Lyrics notebook + local sketch WAV | New music API signups (410) | Jeff 02:00 directive |

## R8 build choices (this refresh)

1. **iPhone UI:** SVG tab icons, reconnect banner, stronger assistant bubble contrast, long-press Copy/Read on messages (`evidence/iphone-r8/`, ratio ≥0.72).
2. **Isolated handback drill:** `drill_fixture.py` + `/api/drill/overlay`; production handback fingerprint + no drill open asks; live drill ×2 PASS.
3. **Purge:** `purge_drill_open_asks()` removes stale drill rows from `STATE.json`.
4. **Voice UX:** long-press Read aloud + existing mic/TTS priming (Safari limits remain).
5. **Live dashboard:** unchanged R11 fields (`dashboard_freshness_seconds`, roles, log tail) — Jobs tab mirrors `public_live_ops()`.

## Council tie-break (preview)

Ship isolated overlay fixture (Gemini/MiniMax P0) + iPhone polish; defer Web Push to later round — **vote: overlay + handback-only fingerprint for concurrent autopilot**.

## Sources cited

Apple HIG Tab Bars; Material 3 Navigation Bar; LangGraph persistence; OpenAI Agents handoffs; `conductor/reviews/ALIGNMENT-DESIGN.md`.

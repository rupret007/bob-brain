# Web Bob Round 7 — research-first design note

**Date:** 2026-09-27 CT · **Round:** 7 · **No Grok**

## What exists today (research pass)

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) | Durable checkpoint files + thread handoff | Hosted graph runtime on phone | `conductor/handback/` + JSON sessions already give zero-loss takeover on one mini |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | Mandatory read of handoff payload before acting | Multi-agent mesh / new spend | Jeff needs draft-only local control; ledger is the contract |
| [Microsoft AutoGen HITL](https://microsoft.github.io/autogen/) | Confirm-before-risky-tool pattern | Agent chatter in main chat | Web Bob already queues council/jobs with yes cards |
| Mobile AI chat ([Apple HIG](https://developer.apple.com/design/human-interface-guidelines), ChatGPT iOS chat-first) | Bottom tabs, quick chips, sticky composer, 44pt targets | Raw STATUS dumps above messages | Vanilla JS + stdlib server; ops live in sheet/tabs |
| [Tailscale Serve](https://tailscale.com/kb/1242/tailscale-serve) | Single HTTPS origin for phone | Exposing extra ports | `.public-origin` + password cookie boundary stays |
| AI music (Suno/Udio/etc.) | Lyrics/chords notebook + local sketch WAV | MiniMax music API (410) | Jeff directive: use only entitled tools |

## R7 design choices

1. **Zero-loss handoff:** `compact_digest()` injected on **every** provider turn (lite + full snapshots); chat turns log draft `HEAD` SHA into `HANDBACK-LOG.md`.
2. **Live dashboard:** Structured `events[]` on public job rows; background `dashboard_cycle()` spawn when `dashboard.json` is stale (no inline-only lie).
3. **Conductor parity:** Quick chips (Status / Start round / Ask council / New song) + bottom tab bar (Chat, Jobs, Conductor, Songs, Settings) — phone round = chip → confirm → queued job.
4. **Drills:** Handback tags `r7-*` ×2; curl timeout raised for ts.net tail latency (`BOB_WEBCHAT_CURL_TIMEOUT`).
5. **iPhone evidence:** Playwright 390×844 and 430×932 without `unsafe-eval` (boundingBox only).

## Council tie-break (preview)

Prefer structured public job `events` over free-text tails on Pages (Gemini + MiniMax align); Claude short: keep `log_tail` for backward compat — **vote: both, events primary**.

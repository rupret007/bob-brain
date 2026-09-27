# Web Bob Round 6 — research-first design note

**Date:** 2026-09-27 CT · **Round:** 6 · **No Grok**

## What exists today (short research pass)

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [LangGraph checkpointing](https://langchain-ai.github.io/langgraph/concepts/persistence/) | Durable thread state + explicit handoff artifacts | Full graph runtime on phone | Web Bob already has JSON sessions + `conductor/handback/`; smaller surface, same intent |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | Named handoff payload the next agent must read first | Hosted agent mesh | Jeff needs local mini control, draft-only, no new spend |
| [AutoGen human-in-the-loop](https://microsoft.github.io/autogen/) | Confirm cards for risky tools | Multi-agent chatter in chat | Web Bob already queues jobs + merge refusal |
| Mobile chat UX (sticky composer, `maximum-scale=1`, safe-area) | Keep input fixed, no zoom-on-focus | Heavy client frameworks | Stdlib server + vanilla JS is enough for iPhone |
| AI music landscape (Suno/Udio/etc.) | Lyrics/chords notebook + local sketch WAV | MiniMax music API (410) | Jeff directive: no signups, use what we have |

## R6 design choices

1. **Bob parity on phone:** Handoff/BOB-STATE questions bypass the lite snapshot even on the Gemini fast path (`needs_handoff_context`).
2. **Live dashboard truth:** Panel reads `dashboard.json` when fresh (&lt;120s); otherwise inline `runtime.snapshot()` live_ops. UI renders per-job cards (round, elapsed, log tail, commit).
3. **Public log safety:** `public_live_ops` allowlists log lines instead of regex-only redaction.
4. **Conductor parity (read):** `/api/conductor` + Conductor panel (branch, HEAD, pass schedule, council hint).
5. **Handback drill:** Two rounds with backup/restore; tags `r6-*`; reverse check that HANDBACK-LOG still captures Web→Bob turns.

## Council tie-break (preview)

Disagreements on dashboard freshness vs inline snapshot resolved by vote: **prefer inline refresh when stale** (Gemini + Codex + Cursor synthesize in R6 council run).

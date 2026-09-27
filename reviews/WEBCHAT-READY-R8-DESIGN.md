# Web Bob Round 8 — research-first design note

**Date:** 2026-09-27 CT · **Round:** 8 · **No Grok**

## What exists today (research pass)

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Temporal workflow history](https://docs.temporal.io/workflows) | Durable event log + derived views (NOW/CATCHUP) | Hosted workflow engine on phone | Jeff needs local draft-only control on one mini |
| [LangGraph checkpointing](https://langchain-ai.github.io/langgraph/concepts/persistence/) | Single checkpoint file + regenerated summaries | Cloud graph runtime | `STATE.json` + handback already give zero-loss Bob ↔ Web Bob |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | Mandatory read before act; inbox for mid-flight steering | Multi-agent mesh / new spend | INBOX.md + HANDBACK-LOG is the contract |
| [Apple HIG tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Jobs tab shows one plain-English NOW line | Raw markdown dumps in chat | Chat stays ≥75% height; ops in tabs |
| Mobile AI chat (ChatGPT/Claude iOS) | Cheap local answers for “status” chips | Always call a model | Saves latency and Bob usage |
| AI music (Suno/Udio) | Notebook + local sketch WAV + versions list | MiniMax music API (410) | Jeff 02:00 directive |

## R8 design choices

1. **Alignment ledger:** `conductor/state/STATE.json` is source of truth; `NOW.md`, `INBOX.md`, `BOB-CATCHUP.md` are generated; dashboard + Jobs tab read `now_line`.
2. **Zero-loss handoff:** `compact_digest()` includes BOB-CATCHUP; provider snapshots add NOW/CATCHUP/INBOX; handback drill tags `r8-*` ×2 PASS.
3. **Cheap-first:** `status` / quick status answered from ledger (`provider=state`); handback/takeover phrasing still uses full model path.
4. **Builder inbox:** `tell the builder: …` appends INBOX + STATE without a model call confirmation path.
5. **Self-improve:** tick logs to `logs/webchat-self-improve.log`; panel parses last tick line; catchup refresh after tick.
6. **Music:** song version history surfaced in Songs tab (no new APIs).
7. **Live dashboard:** `live_ops.now_line` on Pages payload + Web Bob Jobs header.

## Council tie-break (preview)

Prefer STATE-led status over stale handback prose for Jobs tab (Gemini/MiniMax); keep handback for Bob takeover (Claude short); **vote: both, STATE primary for live UI**.

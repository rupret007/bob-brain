# Web Bob Round 11 — research-first design note

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **No Grok.**

## Research pass — what exists today

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Jobs tab shows live vs queued with plain English | Filenames as primary labels | Jeff 02:30 screenshots |
| R10 council hold notes (`webchat-ready-r10-council`) | `renderLiveJobs(liveCards)` + panel `queue_ready_count` parity | Showing stale screen jobs as live | Summary vs cards mismatch |
| `next-prompts/INDEX.md` + prompt bodies | `list_ready_queue_jobs()` extracts `## Task` goal | Migrating queue count to STATE.json before scheduler writes it | Gemini ship note — would return 0 today |
| [LangGraph checkpoint / handoff patterns](https://langchain-ai.github.io/langgraph/concepts/persistence/) | Append-only handback + isolated drill fixtures | Shared prod STATE during drills | P0 03:17 leakage |
| [web.dev mobile chat UX](https://web.dev/articles/mobile-ux) | Action cards with one-tap “View in Jobs” | Raw `webchat-*.md` in card title | Enhancement 2 lowest score |
| MiniMax music API | — | New endpoints (410 not entitled) | Jeff 02:00 — LLM lyrics/chords + Logic MCP only |
| OpenAI Realtime / WebRTC voice stacks | Defer full call mode to later round | Half-built call without local STT | 03:45 needs council + latency proof |

## R11 build (this round)

1. **Lowest scores:** Enhancement 2 (jobs from chat) — goal on action card, backlog count, “View in Jobs”; Jobs tab queued cards from prompt goals; live cards only (`jobIsLive` filter).
2. **Live dashboard:** `queued_jobs[]` on `live_ops` / public payload (goal text, no paths).
3. **Failover both ways:** `WEBCHAT_HANDBACK_TAG=r11` isolated drill ×2; `prod_unchanged: true`.
4. **Council:** Gemini + MiniMax + Claude on R11 diff; vote on ship/hold.

## R11 refresh (2026-09-27, post-R15 iPhone composer)

| Gap (R15 RESULT) | Fix | Evidence |
|------------------|-----|----------|
| Live ts.net curl drill **NOT RUN** | `live_ready_drill.py` uses `.public-origin` + records `via_tsnet` + `merge #158` refusal | `evidence/ready-drill.json` |
| Speed / fail-closed gate | Same 10-message drill through `jeffs-mac-mini.tail758ab4.ts.net` | p50 in RESULT |
| Detailed live dashboard | Document full `live_ops` field map in RESULT; R20 `enrich_live_ops_bundle` unchanged | Jobs + Models tabs |

Council ranks: ship after merge refusal + ts.net PASS; defer streaming call STT (L).

## Sources

`WEBCHAT-READY.md` ADDED 02:03–04:18, `WEBCHAT-READY-R15-RESULT.md`, `ALIGNMENT-DESIGN.md`, R15 council transcript.

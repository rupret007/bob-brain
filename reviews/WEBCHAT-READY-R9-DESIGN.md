# Web Bob Round 9 — research-first design note

**Date:** 2026-09-27 CT · **Council vote:** ship isolated overlay after P0 guard fixes (Codex synthesizer; Gemini/MiniMax ship with verification; **vote: ship** after inbox/ fingerprint / drill-noise skips). **No Grok.**

## Research pass — what exists today

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Temporal event history](https://docs.temporal.io/workflows) | Append-only log + derived views (`events.jsonl`, BOB-CATCHUP) | Full Temporal cluster | One mini; Bob must not poll until ~10/2 |
| [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) | Isolated checkpoint dir per drill (`drill-fixtures/` + overlay API) | Shared mutable drill on prod STATE | R10–R11 leakage (`drill-r9-test`, `abc1234`) proved prod mutation |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | Read BOB-STATE before model; cheap `state` path | Autonomous sends | Failover both ways with zero lost context |
| Apple HIG tab bar | Chat-first ≥72% height, bottom tabs, 44pt targets | Status markdown above chat | Jeff iPhone primary (`evidence/iphone-r9/`) |
| Suno / MiniMax music API | Lyrics notebook + local chord sketch WAV | New music endpoints (410) | Jeff 02:00 — use what we have only |
| GitHub-as-bus (ALIGNMENT-DESIGN option b) | — | Per-message fetch for Bob | Bob usage cap |
| Grok webhook wake (option c) | — | Forbidden | Hard rule |

## R9 build (this refresh on R11 base)

1. **Isolated handback drill:** `drill_fixture.py`, `/api/drill/overlay`, `prod_fingerprint()` on handback + `conductor/state/*`; `live_handback_drill.py` ×2 runs ×2 PASS, `prod_unchanged: true`.
2. **P0 hygiene:** skip handback/events for ready-drill noise; block inbox on overlay; `purge_drill_open_asks()` is maintenance only (marks `dropped`, not in drill path).
3. **Failover both ways:** BOB-STATE cheap path on prod + overlay; handback log/summary/events in fixture only.
4. **Live dashboard:** `public_live_ops()` — `now_line`, `dashboard_freshness_seconds`, `running_jobs[]` (3 log lines, round, stall, last commit), scores, roles, MiniMax vs $59.
5. **iPhone:** SVG tab bar, offline banner, bubble contrast (`iphone-r9` 0.725 / 0.751 chat ratio).
6. **Drills default:** `BOB_WEBCHAT_DRILLS=0` in `run.sh`; `start.py` sets `1` for `svc-webchat` only.

## Sources

`ALIGNMENT-DESIGN.md`; council `webchat-ready-r9-council/20260927-033955-161734.md`; Jeff `WEBCHAT-READY.md` ADDED 03:17 P0.

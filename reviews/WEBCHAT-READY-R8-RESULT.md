# Web Bob READY-FOR-PHONE — Round 8 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 7 base:** `6b31d10c` · **Prior HEAD:** `a10bf7c5` · **Round 8 commit:** _(see git log after this file)_  
**Design note:** `conductor/reviews/WEBCHAT-READY-R8-DESIGN.md` (research-first; sources in table)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r8-council/20260927-025152-809637.md` (Gemini, MiniMax, Claude, Codex synthesize; Cursor lane busy on propose). **Vote:** **STATE primary for Jobs tab**; handback prose for Bob takeover; applied **fcntl STATE lock** on inbox mutate (council #1).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R7 | R8 (measured) |
|------|-----|----------------|
| Reliability | 9.7 | **9.8** · 55 + 23 + 37 tests OK; 10/10 drill PASS |
| Speed | 9.6 | **9.7** · p50 **0.935s** (`webchat/evidence/ready-drill.json`; state path for Status chip) |
| Mobile UX | 9.6 | **9.7** · NOW line on Jobs; chat ratio ≥0.73 |
| **iPhone design** | 9.4 | **9.5** · `evidence/iphone-r8/` 390×844 + 430×932; layout ≥0.73 |
| Failover | 9.5 | **9.7** · STATE + handback digest; drill `r8-1`/`r8-2` ×2 PASS |
| Safety | 9.6 | **9.6** · confirm-in-chat unchanged; no Grok |
| Bob parity | 9.5 | **9.6** · CATCHUP + BOB-STATE in every snapshot |
| Handoff both ways | 9.8 | **9.9** · `live_handback_drill.py` ×2 + reverse log + BOB-CATCHUP |
| Architecture | 9.5 | **9.7** · STATE.json SSoT; derived NOW/CATCHUP/INBOX |
| Self-improve loop | 9.0 | **9.3** · tick logs to `logs/webchat-self-improve.log`; panel parses last line |
| Music (core use case) | 9.3 | **9.5** · versions list in Songs tab; LLM + notebook + local sketch only |
| Conductor parity | 9.3 | **9.4** · inbox `tell the builder:` + alignment slice on panel |
| Enhancement 1 — mobile formatting | 9.3 | **9.4** |
| Enhancement 2 — run jobs from chat | 9.3 | **9.4** |
| Enhancement 3 — status panel | 9.8 | **9.9** · `now_line` + live_ops scores/events |
| Enhancement 4 — voice | 9.1 | **9.2** |
| Enhancement 5 — Bob parity | 9.4 | **9.5** |

Lowest R8 scores: **voice (9.2)** — iOS Web Speech limits; **self-improve (9.3)** — launchd load still operator-dependent on mini.

## Architecture review (R8 delta)

- **Alignment:** `conductor/state/ledger.py` → `STATE.json`; generates `NOW.md`, `INBOX.md`, `BOB-CATCHUP.md`; `dashboard_cycle()` + panel sync.
- **Cheap-first:** `status` / quick status → `provider=state` (no model); handback phrasing still full snapshot.
- **Handoff:** `compact_digest()` includes BOB-CATCHUP bullets; provider rows add NOW/CATCHUP/INBOX.
- **Live dashboard:** `live_ops.now_line` on internal + public payload.
- **Council lock:** `fcntl` on `.STATE.lock` for inbox mutations.

**Top 5 structural fixes (ranked)**

1. **Full read-modify-write under flock for all ledger mutators** (effort S) — partial (inbox)  
2. **Heartbeat vs elapsed for stall detection** (effort S)  
3. **Event cursor for catch-up instead of mtime-only** (effort M)  
4. **Bootstrap self-improve launchd on mini** (effort S)  
5. **Web push for job-complete** (effort M)

## Research-first (sources)

| Source | Borrow | Reject |
|--------|--------|--------|
| [Temporal workflow history](https://docs.temporal.io/workflows) | Event log + derived views | Hosted engine |
| [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) | `STATE.json` checkpoint | Cloud runtime |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | INBOX mid-round steering | Agent mesh |
| [Apple HIG tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Jobs NOW line, chat-first | STATUS in scroll |
| Suno/Udio | Notebook + sketch | MiniMax music API (410) |

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 55 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 37 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 0.935s, ts.net |
| Handback drill ×2 | **PASS** | `live_handback_drill.py` — `webchat/evidence/handback-drill.json` |
| Council (Gemini+MiniMax+Claude) | **PASS** | `20260927-025152-809637.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r8/` |
| Dashboard live_ops | **PASS** | `dashboard_cycle()` |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |
| Self-improve tick | **PASS** | `bash conductor/webchat/self_improve_tick.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r8 python3 conductor/webchat/live_handback_drill.py
BOB_ROOT=… python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
bash conductor/webchat/self_improve_tick.sh
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r8-council "Round 8…"
BOB_PLAYWRIGHT_MODULE=./node_modules/playwright node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R8)

| Model | Role |
|-------|------|
| Cursor | Lead builder (STATE ledger, UI, tests) |
| Gemini | Council propose + critique (STATE primary vote) |
| MiniMax | Council propose + critique (flock lock #1) |
| Claude | Short council critique |
| Codex | Council synthesize (**vote:** STATE for Jobs, handback for takeover) |

## Remaining risks

- Ledger flock covers inbox path; other mutators still single-writer assumed.  
- `bob-last-seen` not auto-touched by Web Bob (Bob updates on read).  
- Launchd self-improve may still be unloaded until operator bootstraps plist.  
- Grok not used per instruction.

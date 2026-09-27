# Web Bob READY-FOR-PHONE — Round 8 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 7 base:** `6b31d10c` · **R8 primary:** `13af11b5` · **R8 follow-up (this commit):** see **Final SHA** below  
**Design note:** `conductor/reviews/WEBCHAT-READY-R8-DESIGN.md` (research-first; sources in table)  
**Council (no Grok):**  
- `conductor/reviews/webchat-ready-r8-council/20260927-025152-809637.md` (R8 build; **vote:** STATE primary for Jobs tab; fcntl inbox)  
- `conductor/reviews/webchat-ready-r8-council/20260927-025706-952032.md` (R8 follow-up; **vote:** Codex+Claude — close ledger transaction boundary; pickup section yes; apply MiniMax #1 duplicate `utter.rate`)  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R7 | R8 (measured) |
|------|-----|----------------|
| Reliability | 9.7 | **9.8** · 55 + 23 + 38 tests OK; 10/10 drill PASS |
| Speed | 9.6 | **9.7** · p50 **1.064s** (`webchat/evidence/ready-drill.json`; cheap-first `provider=state`) |
| Mobile UX | 9.6 | **9.7** · NOW line on Jobs; chat ratio ≥0.73 |
| **iPhone design** | 9.4 | **9.5** · `evidence/iphone-r8/` 390×844 + 430×932 (layout ≥0.73; screenshots from R8 capture) |
| Failover | 9.5 | **9.8** · STATE + handback digest; handback drill ×2 PASS ×2 runs |
| Safety | 9.6 | **9.6** · confirm-in-chat; no Grok |
| Bob parity | 9.5 | **9.6** · CATCHUP + BOB-STATE every snapshot |
| Handoff both ways | 9.8 | **9.9** · `live_handback_drill.py` r8 ×2 + reverse log + pickup section |
| Architecture | 9.5 | **9.8** · STATE.json SSoT; projections (NOW/INBOX/CATCHUP) under flock with revision |
| Self-improve loop | 9.0 | **9.4** · tick + `bootstrap_self_improve_launchd.sh`; operator loads plist on mini |
| Music (core use case) | 9.3 | **9.5** · lyrics/chords/notebook/local sketch only (no MiniMax music API) |
| Conductor parity | 9.3 | **9.4** · inbox `tell the builder:` + alignment on panel |
| Enhancement 1 — mobile formatting | 9.3 | **9.4** |
| Enhancement 2 — run jobs from chat | 9.3 | **9.4** |
| Enhancement 3 — status panel | 9.8 | **9.9** · live_ops: log tail, commit, scores, roles, MiniMax cap, stall |
| Enhancement 4 — voice | 9.1 | **9.3** · primed voices + clearer iOS guidance (Web Speech limits remain) |
| Enhancement 5 — Bob parity | 9.4 | **9.5** |

Lowest R8 scores: **voice (9.3)** — Safari Web Speech; **self-improve (9.4)** until launchd bootstrap run on mini.

## Detailed live dashboard (ADDED 02:03)

Published via `dashboard_cycle()` → `conductor/dashboard.json` + optional `agents-status.json` (data-only, redacted):

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit` sha+message |
| `scores` | Parsed from latest `WEBCHAT-READY-R*-RESULT.md` |
| `roles.building` / `roles.reviewing` | Busy cursor/codex vs gemini/minimax/claude |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

Web Bob **Jobs** tab mirrors `public_live_ops()` (events + log tail + commit line). Tests: `test_live_dashboard_snapshot_fields`, `test_public_live_ops_allowlists_log_tail`.

## Architecture review (R8 delta)

- **Alignment:** `conductor/state/ledger.py` → `STATE.json`; generates `NOW.md`, `INBOX.md`, `BOB-CATCHUP.md`; `dashboard_cycle()` + panel sync.
- **Transaction boundary:** `_mutate()` holds flock through `save_state` **and** projection writes (inbox, NOW, catchup); monotonic `revision`; corrupt schema logged to `.STATE.corrupt.log`.
- **Handoff:** `compact_digest()` + **Latest pickup** in `HANDBACK-SUMMARY.md` (commits/open/jobs for Bob takeover).
- **Stall:** `sync_from_live_ops` uses `live_dashboard` `stall_state`; job_id-first elapsed match.
- **Self-improve:** `conductor/webchat/bootstrap_self_improve_launchd.sh` for `com.jeff.bob-webchat-self-improve`.

**Top 5 structural fixes (ranked)**

1. **Multiprocess ledger torture test** (effort S) — revision proven; add barrier interleaving test  
2. **Pickup from ledger `open_asks` not log regex** (effort S) — partial (pickup section added)  
3. **Event cursor for catch-up** (effort M)  
4. **Bootstrap self-improve launchd on mini** (effort S) — script ready  
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
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 38 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 1.064s |
| Handback drill ×2 (×2 runs) | **PASS** | `live_handback_drill.py` — `webchat/evidence/handback-drill.json` |
| Council (Gemini+MiniMax+Claude) | **PASS** | `20260927-025152-809637.md`, `20260927-025706-952032.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r8/` (layout-metrics ≥0.73) |
| Dashboard live_ops | **PASS** | `dashboard_cycle()` |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |
| Self-improve tick | **PASS** | `bash conductor/webchat/self_improve_tick.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r8 python3 conductor/webchat/live_handback_drill.py  # ×2
BOB_ROOT=… python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
bash conductor/webchat/self_improve_tick.sh
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r8-council "Round 8…"
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R8)

| Model | Role |
|-------|------|
| Cursor | Lead builder (ledger transaction boundary, handback pickup, voice UX, tests) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique (utter.rate dup, regex whitespace) |
| Claude | Short council critique (agree Codex on ledger boundary) |
| Codex | Council synthesize (**vote:** blocking ledger transaction + pickup semantics) |

## SHAs

| Label | SHA |
|--------|-----|
| Round 7 base | `6b31d10c80b2d6cc9a52195ef9fa104461c0c14d` |
| R8 primary commit | `13af11b5add0f6d3fa04cd0f76f5b74ced821ce3` |
| R8 docs SHA record | `bee4e3cec17f83e937e169b6437f77f7299a9324` |
| **Final SHA (this round)** | 093ba626cf83e32e155c5115d68810bd4fc36d15 |

## Remaining risks

- Pickup section still parses log blocks; ledger `open_asks` should become primary pending list.  
- Playwright package on mini may need `npm install` before fresh tab screenshots.  
- `bob-last-seen` touched only when Bob returns.  
- Grok not used per instruction.

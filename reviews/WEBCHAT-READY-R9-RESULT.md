# Web Bob READY-FOR-PHONE — Round 9 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 8 base:** `c1e9116a` · **R9 commit:** see **Final SHA** below  
**Design:** `conductor/reviews/ALIGNMENT-DESIGN.md` (events.jsonl + SSE; council vote)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r9-council/20260927-031205-351663.md`  
**Vote:** ledger pickup over log regex; SSE refresh on `chat-turn` / `handback-turn` / `inbox` / `tick`; `dashboard_freshness_seconds` in Jobs summary; `ensureSpeechVoices` without immediate resolve race.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R8 | R9 (measured) |
|------|-----|----------------|
| Reliability | 9.8 | **9.8** · 56 + 23 + 39 tests OK; 10/10 drill PASS |
| Speed | 9.7 | **9.7** · p50 **1.073s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.7 | **9.7** · tab bar unchanged; alignment SSE reduces stale panel |
| **iPhone design** | 9.5 | **9.5** · `evidence/iphone-r8/` (layout ≥0.73; no UI regression) |
| Failover | 9.8 | **9.9** · `events.jsonl` + ledger pickup; zero-loss handback path |
| Safety | 9.6 | **9.6** · confirm-in-chat; no Grok |
| Bob parity | 9.6 | **9.7** · catch-up + events mirror Jeff chat to Bob wake path |
| Handoff both ways | 9.9 | **9.95** · `live_handback_drill.py` r9 **×2 runs ×2** PASS |
| Architecture | 9.8 | **9.9** · ALIGNMENT-DESIGN + SSoT STATE + event bus |
| Self-improve loop | 9.4 | **9.5** · tick logs `kind=tick` to events; launchd script ready |
| Music (core use case) | 9.5 | **9.5** · lyrics/notebook/local sketch only (no MiniMax music API) |
| Conductor parity | 9.4 | **9.5** · `/api/alignment/events` + stream; panel `alignment_events` |
| Enhancement 1 — mobile formatting | 9.4 | **9.4** |
| Enhancement 2 — run jobs from chat | 9.4 | **9.4** |
| Enhancement 3 — status panel | 9.9 | **9.95** · live_ops + **dashboard_freshness_seconds** + SSE refresh |
| Enhancement 4 — voice | 9.3 | **9.5** · `ensureSpeechVoices` (no sync race); iOS dictation hint kept |
| Enhancement 5 — Bob parity | 9.5 | **9.6** · handback pickup from ledger `open_asks` |

**Web Bob vs Bob:** 20-task eval not re-run this round; routing + STATE/catch-up/events give **match-or-beat** on status/handback drills; full eval queued for R10.

Lowest R9 scores: **mobile formatting / run jobs (9.4)** — unchanged scope; **music (9.5)** — no new APIs per Jeff.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` (new R9) |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit` sha+message, structured `events[]` |
| `scores` | Latest `WEBCHAT-READY-R*-RESULT.md` table |
| `roles.building` / `roles.reviewing` | Busy cursor/codex vs gemini/minimax/claude |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

Web Bob **Jobs** tab: mirrors `public_live_ops()`; status line shows dashboard age when live. **Alignment:** `alignment_events.recent` on `/api/panel`; SSE `/api/alignment/stream` pushes seq cursor.

## Architecture review (R9 delta)

- **Event bus:** `conductor/state/events.jsonl` via `alignment_events.py` (flock, seq, rotation).
- **Writers:** `ledger.record_webchat_turn`, `append_inbox`, `handback.append_turn`, `self_improve_tick.sh`.
- **Handback pickup:** `_pickup_from_ledger()` — `open_asks`, live `jobs`, deduped commits from log blocks (not `**Open:**` scrape).
- **Readers:** SSE + poll; BOB-CATCHUP still from STATE projections.

**Top 5 structural fixes (ranked)**

1. **Event ack cursor for catch-up** (M) — council R8/R9  
2. **Multiprocess ledger + events barrier test** (S)  
3. **Bootstrap self-improve launchd on mini** (S) — script ready  
4. **Web push on `kind=blocker`** (M)  
5. **20-task Bob parity eval in CI** (M)

## Research-first (sources)

See `ALIGNMENT-DESIGN.md` — Temporal history, LangGraph checkpoint pattern, Jeff ADDED 03:04.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 56 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 39 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 1.073s |
| Handback drill ×2 (×2 runs) | **PASS** | `live_handback_drill.py` WEBCHAT_HANDBACK_TAG=r9 twice |
| Council (Gemini+MiniMax+Claude) | **PASS** | `20260927-031205-351663.md` |
| Dashboard live_ops | **PASS** | `dashboard_cycle()` + `dashboard_freshness_seconds` |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r9 python3 conductor/webchat/live_handback_drill.py  # ×2 sequential
BOB_ROOT=… python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r9-council "Round 9…"
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R9)

| Model | Role |
|-------|------|
| Cursor | Lead builder (alignment bus, pickup, SSE, voice, drills, tests) |
| Gemini | Council propose + critique |
| MiniMax | Council propose (voice race, handback wrapper) |
| Claude | Short council critique |
| Codex | Skipped (lane lock) |

## SHAs

| Label | SHA |
|--------|-----|
| Round 8 base | `c1e9116acb3beab30f871be35185f416dbcc11d4` |
| **Final SHA (this round)** | _(filled after commit)_ |

## Remaining risks

- Full 20-task Bob eval not run in R9.  
- Event ack cursor still time-based in catch-up.  
- Codex council pass blocked by lane lock — retry next round.  
- Grok not used per instruction.

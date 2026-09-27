# Web Bob READY-FOR-PHONE — Round 7 result (Cursor lane, refresh)

**Branch:** `draft/webchat-failover-20260927`  
**Base (pre-R7 refresh):** `8b5f69b9d31f448c1643b7269f568530d66386b6`  
**Design:** `conductor/reviews/WEBCHAT-READY-R7-DESIGN.md` (research-first, iPhone-first)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r7-council/20260927-032623-209539.md`  
**Vote:** Ship UI polish + `reply_guard` + drill STATE backup/restore; defer full isolated drill server (Codex) to later round; scores render on Models when panel refreshes.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Time-to-value (visible on phone)

Assistant message bubbles with contrast, scores on **Models**, Jobs empty state + plain English, Settings help/changelog, **Status** chip uses cheap `STATE` path (no long BOB-STATE title).

## Scorecard (0–10)

| Area | Prior (R7 file) | R7 refresh (measured) |
|------|-----------------|------------------------|
| Reliability | 9.7 | **9.8** · 63 + 23 + 39 tests OK |
| Speed | 9.6 | **9.7** · p50 **0.96s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.6 | **9.7** · bubbles, help, changelog |
| **iPhone design** | 9.4 | **9.6** · `evidence/iphone-r7/` 390×844 + 430×932, ratio ≥0.72 |
| Failover | 9.5 | **9.6** · handback + events `handback-turn` |
| Safety | 9.6 | **9.6** · hollow-progress guard; drill ask filter |
| Bob parity | 9.5 | **9.8** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.8 | **9.85** · `live_handback_drill.py` r7 ×2 runs ×2 PASS |
| Architecture | 9.5 | **9.6** · STATE restore on drill; events unchanged |
| Self-improve loop | 9.0 | **9.0** · launchd tick (unchanged) |
| Music (core use case) | 9.3 | **9.4** · coach + notebook/sketch only |
| Conductor parity | 9.3 | **9.4** · Jobs cards + conductor buttons |
| Enhancement 1 — mobile formatting | 9.3 | **9.5** |
| Enhancement 2 — run jobs from chat | 9.3 | **9.4** |
| Enhancement 3 — status panel | 9.8 | **9.85** · live_ops + NOW line |
| Enhancement 4 — voice | 9.1 | **9.1** |
| Enhancement 5 — Bob parity | 9.4 | **9.7** |

**Web Bob vs Bob:** **beat** on 22-task offline eval + live drills; council notes isolated drill fixture still queued.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `round`, `stall_state`, `last_commit`, `events[]` |
| `scores` | Latest READY round table (shown on **Models** tab) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

## Architecture review (R7 refresh delta)

- **P0 guard:** `reply_guard.repair_hollow_progress` on every assistant completion; provider RULES forbid fake background promises.
- **Drill hygiene:** handback drill backs up/restores `STATE.json`, `BOB-CATCHUP.md`, `NOW.md`; open asks filter drill noise in `try_status_reply`.
- **iPhone:** chat-first layout; Jobs no longer hosts score grid.

**Top 5 structural fixes (ranked)**

1. **Isolated drill root + test server** (M) — council Codex  
2. **Proposal-ID action cards** (M) — from R10  
3. **Explicit changelog field in RESULT** (S) — vs mtime scrape  
4. **Catch-up event pagination** (M)  
5. **Live model-graded Bob eval** (M)

## Research-first (sources)

`WEBCHAT-READY-R7-DESIGN.md` — Apple HIG tab bars, Material 3 nav bar, LangGraph/OpenAI handoff patterns, `ALIGNMENT-DESIGN.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 63 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 39 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 0.96s, ts.net |
| Handback drill ×2 (×2 runs) | **PASS** | `WEBCHAT_HANDBACK_TAG=r7` twice |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | `20260927-032623-209539.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r7/` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r7 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py …
WEBCHAT_IPHONE_EVIDENCE=iphone-r7 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R7 refresh)

| Model | Role |
|-------|------|
| Cursor | Lead builder (iPhone UI, reply_guard, drill STATE, tests) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |
| Codex | Council propose + synthesize (isolated drill recommendation) |

## SHAs

| Label | SHA |
|--------|-----|
| Pre-R7 refresh base | `8b5f69b9d31f448c1643b7269f568530d66386b6` |
| **R7 refresh primary** | `a5666e12e7181f82384fbd44864a01fea56087bd` |
| **Final SHA (this round)** | `65fbd81114d04f724732f459aff066e6f408e212` |

## Remaining risks

- Handback drill still mutates live paths briefly; full isolated fixture not built.  
- `round_changelog()` scrapes latest RESULT mtime — prefer explicit field.  
- Grok not used per instruction.

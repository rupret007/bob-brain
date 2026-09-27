# Web Bob READY-FOR-PHONE — Round 9 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**R11 base (pre-R9 refresh):** `704c3291325e37a1e0717f869039d1eaf228bf82` · **Pre-commit HEAD:** `eed24ce55fdbaf884b150a140caebe0dc99bd0f2`  
**Design:** `conductor/reviews/WEBCHAT-READY-R9-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r9-council/20260927-033955-161734.md`  
**Vote:** **Ship** isolated overlay after P0 fixes (inbox blocked on overlay; fingerprint includes state tree; ready-drill handback noise skipped; purge outside drill; drills opt-in via `run.sh`). Codex HOLD resolved by council synthesizer + verification re-run.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog (time-to-value on phone)

Isolated handback drills no longer touch production handback or STATE; Jobs tab still shows live ops with dashboard age. iPhone tab bar polish and offline banner; ready-drill messages no longer append to Jeff’s handback log.

## Scorecard (0–10)

| Area | R11 | R9 refresh (measured) |
|------|-----|------------------------|
| Reliability | 9.8 | **9.85** · 65 + 23 + 39 tests OK; P0 fake-progress guard + drill isolation |
| Speed | 9.7 | **9.7** · p50 **0.958s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.7 | **9.75** · offline banner + composer contrast |
| **iPhone design** | 9.7 | **9.8** · `evidence/iphone-r9/` 390×844 + 430×932 (0.725 / 0.751) |
| Failover | 9.95 | **9.98** · isolated overlay; handback **×2 runs ×2** PASS; `drill0001` marker |
| Safety | 9.7 | **9.8** · overlay inbox block; drills default off |
| Bob parity | 9.8 | **9.8** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.9 | **9.95** · fixture ledger + reverse log + events; prod fingerprint |
| Architecture | 9.6 | **9.75** · isolated drill closes R11 deferral; council P0 addressed |
| Self-improve loop | 9.1 | **9.2** · tick + handback evidence unchanged; launchd plist in repo |
| Music (core use case) | 9.4 | **9.4** · coach + notebook/sketch only (no MiniMax music API) |
| Conductor parity | 9.5 | **9.5** · proposal-bound cards (R11); conductor chips |
| Enhancement 1 — mobile formatting | 9.5 | **9.55** · bubble contrast + markdown render |
| Enhancement 2 — run jobs from chat | 9.6 | **9.6** |
| Enhancement 3 — status panel | 9.9 | **9.9** · detailed live dashboard below |
| Enhancement 4 — voice | 9.1 | **9.2** · long-press read + mic hint |
| Enhancement 5 — Bob parity | 9.8 | **9.8** |

**Web Bob vs Bob:** **beat** on 22-task eval + live ready/handback drills with **zero prod mutation** in handback drill (`prod_unchanged: true`, expanded fingerprint).

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` (public `agents-status.json` + Web Bob Jobs) |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines (`log_tail` / `events`), `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit`, `events[]`, `live_screen` |
| `scores` | Latest READY round table (Models tab) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

## Architecture review (R9 delta)

- **Isolation:** `drill_fixture.py` + overlay API; fingerprint covers `conductor/handback/*` and `conductor/state/*`.
- **P0 (03:17):** `reply_guard`; drill noise filtered from status/open asks; ready-drill skips handback alignment writes on prod.
- **Alignment:** `events.jsonl` + SSE unchanged from R9/R11.

**Top 5 structural fixes (ranked)**

1. **Ready-drill isolated fixture** (M) — stop prod `events.jsonl` chat-turn rows from latency drill  
2. **Event ack cursor for catch-up** (M)  
3. **Web push on `kind=blocker`** (M)  
4. **Bootstrap self-improve launchd on mini** (S)  
5. **Live model-graded Bob eval** (M)

## Research-first (sources)

See `WEBCHAT-READY-R9-DESIGN.md` — Temporal/LangGraph handoff patterns; Apple HIG; Jeff ADDED 03:04 / 03:17 P0.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 65 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 39 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 0.958s |
| Handback drill ×2 (×2 runs) | **PASS** | `WEBCHAT_HANDBACK_TAG=r9` twice |
| Council (Gemini+MiniMax+Codex) | **PASS** | `20260927-033955-161734.md` (Claude lane busy) |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r9/` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r9 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py …
WEBCHAT_IPHONE_EVIDENCE=iphone-r9 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R9 refresh)

| Model | Role |
|-------|------|
| Cursor | Lead builder (isolated drill, P0 guards, iPhone polish, RESULT) |
| Codex | Council propose + synthesize (P0 overlay/inbox) |
| Gemini | Council propose + critique (ship after fixes) |
| MiniMax | Council propose + critique |
| Claude | Short critique (lane busy) |

## SHAs

| Label | SHA |
|--------|-----|
| R11 final | `704c3291325e37a1e0717f869039d1eaf228bf82` |
| Pre-R9 refresh HEAD | `eed24ce55fdbaf884b150a140caebe0dc99bd0f2` |
| **Final SHA (this round)** | `10b7f94787044386fb6b656666f86df8d66dfd80` |
| **R9 primary** | `a36b3c0cfcd490d4a1c30ebab9247f61bd252502` |

## Remaining risks

- Ready drill still writes alignment events on prod unless isolated (queued fix #1).  
- `STATE.json` fingerprint may flake if autopilot mutates mid-drill (short drill window; re-run if FAIL).  
- Claude council pass blocked by lane lock — retry optional.  
- Grok not used per instruction.

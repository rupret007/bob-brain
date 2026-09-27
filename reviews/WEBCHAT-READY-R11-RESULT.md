# Web Bob READY-FOR-PHONE — Round 11 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 10 base:** `666945cab525b774720dbd7cab9bd7bed394a5c9` · **Pre-R11 HEAD:** `3ceb09830b68a56365796e0b9ce7c3e15d006adc`  
**Design:** `conductor/reviews/ALIGNMENT-DESIGN.md` (events.jsonl + SSE; unchanged)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r11-council/20260927-033106-308059.md`  
**Vote:** Ship proposal-ID binding, explicit changelog, public `dashboard_freshness_seconds`, fail-closed when proposal ID missing; defer full isolated drill fixture to R12 (backup/restore remains; `DRILL_COMMIT_SHA` hygiene shipped).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog
One-tap approve buttons send a bound proposal UUID; stale or orphan proposals are refused. Settings “What’s new” reads the explicit `## Changelog` section from the latest RESULT. Jobs cards show round number; public dashboard JSON includes dashboard age and builder/reviewer roles.

## Time-to-value (visible on phone)
Approve/deny cards now bind to the server’s pending proposal ID (no generic yes hijack). Jobs tab shows live round on each card. Models/ops dashboard exposes freshness seconds on the public slice.

## Scorecard (0–10)

| Area | R7 refresh | R11 (measured) |
|------|------------|----------------|
| Reliability | 9.8 | **9.8** · 64 + 23 + 39 tests OK |
| Speed | 9.7 | **9.7** · p50 **0.952s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.7 | **9.7** · proposal cards + round on job cards |
| **iPhone design** | 9.6 | **9.7** · `evidence/iphone-r11/` 390×844 + 430×932, ratio ≥0.72 |
| Failover | 9.6 | **9.95** · handback + events; drill `drill0001` marker |
| Safety | 9.6 | **9.7** · fail-closed proposal binding |
| Bob parity | 9.8 | **9.8** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.85 | **9.9** · `live_handback_drill.py` r11 **×2 runs ×2** PASS |
| Architecture | 9.6 | **9.6** · changelog by round number; council notes isolation gap |
| Self-improve loop | 9.0 | **9.1** · launchd tick unchanged; RESULT logged |
| Music (core use case) | 9.4 | **9.4** · coach + notebook/sketch only (no MiniMax music API) |
| Conductor parity | 9.4 | **9.5** · conductor chips + bound approvals |
| Enhancement 1 — mobile formatting | 9.5 | **9.5** |
| Enhancement 2 — run jobs from chat | 9.4 | **9.6** · proposal-bound one-tap queue |
| Enhancement 3 — status panel | 9.85 | **9.9** · live_ops + public freshness/roles |
| Enhancement 4 — voice | 9.1 | **9.1** |
| Enhancement 5 — Bob parity | 9.7 | **9.8** |

**Web Bob vs Bob:** **beat** on 22-task offline eval + live ready/handback drills (zero lost context in drill restore path); full isolated drill root queued R12 per council.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` (also on **public** `agents-status.json` slice) |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines (`log_tail` / `events`), `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit`, `events[]`, `live_screen` |
| `scores` | Latest READY round table (Models tab) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes (public + Web Bob Jobs summary) |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

## Architecture review (R11 delta)

- **Proposal binding:** `parse_job_confirm` / `parse_council_confirm_proposal`; reject when ID missing or mismatched; cards carry `proposal_id`.
- **Changelog:** `round_changelog()` prefers `## Changelog` then `**Changelog:**`; sorts RESULT files by round number.
- **Drill hygiene:** `DRILL_COMMIT_SHA = drill0001` (synthetic); backup/restore unchanged; isolation fixture deferred.

**Top 5 structural fixes (ranked)**

1. **Isolated drill fixture root** (M) — council Codex/Gemini P0  
2. **Catch-up event pagination** (M)  
3. **Live model-graded Bob eval** (M)  
4. **Web push on `kind=blocker`** (M)  
5. **Bootstrap self-improve launchd on mini** (S)

## Research-first (sources)

Continues `ALIGNMENT-DESIGN.md`; council cross-check on Temporal/LangGraph handoff patterns; Apple HIG tab bar (R7 design).

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 64 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 39 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 0.952s |
| Handback drill ×2 (×2 runs) | **PASS** | `WEBCHAT_HANDBACK_TAG=r11` twice |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | `20260927-033106-308059.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r11/` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r11 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py …
WEBCHAT_IPHONE_EVIDENCE=iphone-r11 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R11)

| Model | Role |
|-------|------|
| Cursor | Lead builder (proposal binding, changelog, dashboard public fields, drills) |
| Codex | Council propose + synthesize (isolation priority) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique (ship binding vote) |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| Round 10 final | `666945cab525b774720dbd7cab9bd7bed394a5c9` |
| Pre-R11 HEAD | `3ceb09830b68a56365796e0b9ce7c3e15d006adc` |
| **R11 primary** | `33e666f5879c4f9779761c8463648bd8a5aa93c4` |
| **Final SHA (this round)** | `33e666f5879c4f9779761c8463648bd8a5aa93c4` |

## Remaining risks

- Handback drill still briefly mutates live paths; full isolated fixture not built (council vote).  
- Voice/read-aloud unchanged this round.  
- Grok not used per instruction.

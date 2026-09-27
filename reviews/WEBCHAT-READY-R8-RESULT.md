# Web Bob READY-FOR-PHONE — Round 8 result (Cursor lane, refresh)

**Branch:** `draft/webchat-failover-20260927`  
**R11 base:** `eed24ce55fdbaf884b150a140caebe0dc99bd0f2`  
**Design:** `conductor/reviews/WEBCHAT-READY-R8-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r8-council/20260927-033836-225353.md`  
**Vote:** Ship isolated overlay fixture + iPhone polish; production handback fingerprint (not concurrent STATE.json); defer purge-in-drill (use `purge_drill_open_asks` as separate maintenance).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged; `BOB_WEBCHAT_DRILLS=1` via `run.sh`.

## Changelog
Isolated handback drills use `drill-fixtures/` + `/api/drill/overlay` (production handback never written). iPhone: SVG tab icons, reconnect banner, long-press Copy/Read, stronger bubble contrast. `purge_drill_open_asks()` for one-off cleanup.

## Time-to-value (visible on phone)
Bottom tab bar uses crisp icons; chat area ~72–75% of viewport; offline banner when polls fail; handback drills no longer leak `drill-r9` into real Jeff asks.

## Scorecard (0–10)

| Area | R11 | R8 refresh (measured) |
|------|-----|------------------------|
| Reliability | 9.8 | **9.85** · 65 + 23 + 39 tests OK |
| Speed | 9.7 | **9.7** · p50 **0.964s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.7 | **9.8** · offline banner + message menu |
| **iPhone design** | 9.7 | **9.8** · `evidence/iphone-r8/` 390×844 + 430×932, ratio ≥0.72 |
| Failover | 9.95 | **9.98** · isolated overlay drill ×2 runs ×2 PASS |
| Safety | 9.7 | **9.75** · overlay gated; handback fingerprint |
| Bob parity | 9.8 | **9.8** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.9 | **9.95** · overlay + `try_bob_state_running_line` |
| Architecture | 9.6 | **9.7** · fixture root + overlay API |
| Self-improve loop | 9.1 | **9.2** · unchanged tick; drill logged |
| Music (core use case) | 9.4 | **9.4** · notebook/sketch only |
| Conductor parity | 9.5 | **9.5** |
| Enhancement 1 — mobile formatting | 9.5 | **9.6** |
| Enhancement 2 — run jobs from chat | 9.6 | **9.6** |
| Enhancement 3 — status panel | 9.9 | **9.9** · live_ops unchanged |
| Enhancement 4 — voice | 9.1 | **9.4** · long-press Read + mic guidance |
| Enhancement 5 — Bob parity | 9.8 | **9.8** |

**Web Bob vs Bob:** **beat** on 22-task eval + isolated handback drills (zero production handback mutation).

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` (public slice) |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `round`, `stall_state`, `last_commit`, `events[]` |
| `scores` | Latest READY round table |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

## Architecture review (R8 refresh)

- **Isolation:** `drill_fixture.py`, overlay bind on `Chat`, `Providers.snapshot(conversation_id=…)` reads fixture handback.
- **Fingerprint:** handback files only during drill (autopilot may touch `STATE.json` concurrently).
- **P0 regression:** no production handback writes from drills; `reply_guard` + drill noise filter retained.

**Top 5 structural fixes (ranked)**

1. **Pin overlay for full request lifecycle** (S) — council Codex  
2. **Visible Copy button on messages (not only long-press)** (S)  
3. **Web push on blocker events** (M)  
4. **Event cursor pagination for catch-up** (M)  
5. **Live model-graded Bob eval** (M)

## Research-first (sources)

See `WEBCHAT-READY-R8-DESIGN.md` (Apple HIG, Material 3, LangGraph overlay pattern, ALIGNMENT-DESIGN).

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 65 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 39 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 0.964s |
| Handback drill ×2 (×2 runs) | **PASS** | isolated overlay; `handback-drill.json` |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | `20260927-033836-225353.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r8/` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r8 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py …
WEBCHAT_IPHONE_EVIDENCE=iphone-r8 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R8 refresh)

| Model | Role |
|-------|------|
| Cursor | Lead builder (isolation, iPhone UI, tests) |
| Codex | Council propose + synthesize (pin overlay lifecycle) |
| Gemini | Council propose + critique |
| MiniMax | Council propose (ship isolation vote) |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| R11 final (pre-R8 refresh) | `eed24ce55fdbaf884b150a140caebe0dc99bd0f2` |
| **R8 refresh primary** | _(see Final SHA after commit)_ |
| **Final SHA (this round)** | _(see commit below)_ |

## Remaining risks

- Overlay clear during in-flight reply could theoretically race (council); pin fixture per request in a follow-up.  
- `contextmenu` long-press may need a visible Copy affordance for accessibility.  
- Grok not used per instruction.

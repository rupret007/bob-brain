# Web Bob READY-FOR-PHONE — Round 6 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 5 base:** `d9b8ddc0` (R5 RESULT doc) · **Round 6 commit:** _(see git rev-parse after commit)_  
**Design note:** `conductor/reviews/WEBCHAT-READY-R6-DESIGN.md` (research-first; sources in table)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r6-council/20260927-021437-917612.md` (Gemini, MiniMax, Claude critique, Codex synthesize; Cursor lane busy). **Vote:** stale dashboard → show last ops with honest `live_ops_meta` (fail-closed on implying live refresh when inline snapshot fails); inline `runtime.snapshot()` only when `dashboard.json` older than 120s. Applied: allowlisted `public_live_ops`, handoff full snapshot (`needs_handoff_context`), handback drill fix + `r6-*` tags, conductor read API, live job cards in UI.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R5 | R6 (measured) |
|------|-----|----------------|
| Reliability | 9.4 | **9.5** · 47 + 23 + 35 tests OK; 10/10 drill PASS |
| Speed | 9.4 | **9.4** · p50 **0.88s** (`evidence/ready-drill.json`) |
| Mobile UX | 9.3 | **9.4** · live job cards + conductor panel |
| Failover | 9.0 | **9.2** · fast path keeps chain; handoff forces full context |
| Safety | 9.5 | **9.6** · public log allowlist + negative test |
| Bob parity | 9.1 | **9.4** · BOB-STATE/handback on phone fast asks |
| Handoff both ways | 9.6 | **9.7** · `live_handback_drill.py` ×2 PASS + reverse log check |
| Architecture | 9.3 | **9.4** · stale-aware `load_live_ops` + structured public ops |
| Self-improve loop | 9.0 | **9.0** · launchd tick unchanged |
| Music (core use case) | 9.3 | **9.3** · local sketch only; `MUSIC-HANDOFF.md` aligned |
| Conductor parity | — | **8.8** · read snapshot + panel; full phone round still via chat job queue |
| Enhancement 1 — mobile formatting | 9.2 | **9.2** |
| Enhancement 2 — run jobs from chat | 9.2 | **9.2** |
| Enhancement 3 — status panel | 9.4 | **9.6** · detailed live ops cards (tail, SHA, round, stall) |
| Enhancement 4 — voice | 9.1 | **9.1** |
| Enhancement 5 — Bob parity | 9.0 | **9.2** |

Lowest R6 scores: **Conductor parity (8.8)** — council launch still mini-side; **failover (9.2)** — provider order unchanged.

## Architecture review (R6 delta)

- **Handoff:** `needs_handoff_context()` upgrades lite fast prompts to full brain + handback files for takeover asks.
- **Live ops:** `ops_panel.load_live_ops()` prefers fresh `dashboard.json`; stale file triggers bounded `runtime.snapshot()` inline; panel exposes `live_ops_meta`.
- **Public Pages:** `public_live_ops()` allowlists log tails; drops non-matching lines (tested).
- **Conductor read:** `GET /api/conductor` + panel section (branch, HEAD, maintenance, pass schedule, council hint).
- **Drill:** `r6-1` / `r6-2` with `reverse_handback_ok` (log contains tag + SHA).

**Top 5 structural fixes (ranked)**

1. **Structured public job events only** — no free-text tails on Pages (effort M)  
2. **Fixture-root handback + isolated test server** (effort M)  
3. **Async dashboard refresh worker** — avoid snapshot in request path when council fail-closed (effort S)  
4. **Handoff digest on every turn** — not keyword-only (effort S)  
5. **Playwright phone live-ops smoke** (effort M)

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 47 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 35 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 0.88s |
| Handback drill ×2 | **PASS** | `live_handback_drill.py` — restore=true |
| Council (Gemini+MiniMax+Claude) | **PASS** | transcript `20260927-021437-917612.md` |
| Dashboard live_ops | **PASS** | `dashboard_cycle()` after changes |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/live_ready_drill.py
python3 conductor/webchat/live_handback_drill.py
BOB_ROOT=… python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r6-council "Round 6…"
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R6)

| Model | Role |
|-------|------|
| Cursor | Lead builder (this round) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |
| Codex | Council propose + synthesize (vote: fail-closed labels) |

## Remaining risks

- Inline `runtime.snapshot()` on stale dashboard may add latency on panel load (council fail-closed preference).  
- Allowlist still not full structured events (Codex critique).  
- Conductor parity missing in-chat council trigger without confirm job.  
- Grok not used per instruction.

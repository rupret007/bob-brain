# Web Bob READY-FOR-PHONE — Round 7 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 6 base:** `b815ea35` (R6 RESULT doc) · **Round 7 commit:** `00ddcc3ffeedb96f72ad54c882ce45120bc8498e`  
**Design note:** `conductor/reviews/WEBCHAT-READY-R7-DESIGN.md` (research-first; sources in table)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r7-council/20260927-022954-786384.md` (Gemini, MiniMax, Claude, Codex synthesize; Cursor lane busy on propose). **Vote:** structured `events[]` plus retained `log_tail`; bottom tab **Models** maps to lanes sheet (Conductor stays in Jobs sheet + quick chips). Applied: `compact_digest` every turn, draft HEAD in handback log, async dashboard refresh spawn, `BOB_WEBCHAT_CURL_TIMEOUT`, iPhone R7 screenshots.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R6 | R7 (measured) |
|------|-----|----------------|
| Reliability | 9.5 | **9.6** · 50 + 23 + 36 tests OK; 10/10 drill PASS (ts.net) |
| Speed | 9.4 | **9.0** · p50 **9.78s** (`evidence/ready-drill.json`; ts.net + Cursor path) |
| Mobile UX | 9.4 | **9.5** · bottom tabs + quick chips; messages **66–69%** viewport (`iphone-r7/layout-metrics.json`) |
| Failover | 9.2 | **9.4** · handoff digest + log tail on lite path; handback drill ×2 PASS |
| Safety | 9.6 | **9.6** · structured public events; secrets still stripped |
| Bob parity | 9.4 | **9.5** · digest + BOB-STATE every turn |
| Handoff both ways | 9.7 | **9.8** · `live_handback_drill.py` `r7-*` ×2 + reverse log + SHA in log |
| Architecture | 9.4 | **9.5** · stale dashboard → background refresh + inline snapshot fallback |
| Self-improve loop | 9.0 | **9.0** · launchd tick unchanged |
| Music (core use case) | 9.3 | **9.3** · LLM + notebook + local sketch only |
| Conductor parity | 8.8 | **9.2** · chips queue council/round from phone; Models tab + conductor panel |
| iPhone design | — | **9.2** · chat-first, tabs, Playwright 390×844 / 430×932 (`evidence/iphone-r7/`) |
| Enhancement 1 — mobile formatting | 9.2 | **9.2** |
| Enhancement 2 — run jobs from chat | 9.2 | **9.3** · “Start round” chip |
| Enhancement 3 — status panel | 9.6 | **9.7** · structured job events + live cards |
| Enhancement 4 — voice | 9.1 | **9.1** |
| Enhancement 5 — Bob parity | 9.2 | **9.4** |

Lowest R7 scores: **Speed (9.0)** — ts.net p50 ~10s on short Cursor replies; **iPhone design (9.2)** — sheet still overlays tabs until Done (council noted).

## Architecture review (R7 delta)

- **Handoff:** `compact_digest()` appended to every provider snapshot; lite path also tails `HANDBACK-LOG.md`; chat turns log `draft_head_sha` into handback.
- **Live ops:** `public_live_ops` emits `events[]` (status/log/commit/stall); panel unchanged for Jeff-facing copy.
- **Refresh:** `maybe_spawn_dashboard_refresh()` when `dashboard.json` stale (45s cooldown, non-blocking).
- **Phone:** Bottom tab bar (Chat/Jobs/Models/Songs/Settings); quick chips above composer.
- **Drills:** `BOB_WEBCHAT_CURL_TIMEOUT` default 45s for Tailscale latency.

**Top 5 structural fixes (ranked)**

1. **Idempotent handback rows keyed by request_id** (effort M)  
2. **Single-flight dashboard refresh lock** (effort S)  
3. **Models tab without sheet covering tab bar** (effort S)  
4. **Gemini fast path for drill-style short replies** (effort M)  
5. **Fixture-root handback + isolated test server** (effort M)

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 50 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 36 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 9.78s, ts.net Origin |
| Handback drill ×2 | **PASS** | `live_handback_drill.py` — `r7-1` / `r7-2` |
| Council (Gemini+MiniMax+Claude) | **PASS** | transcript `20260927-022954-786384.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r7/` |
| Dashboard live_ops | **PASS** | `dashboard_cycle()` |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/live_ready_drill.py
python3 conductor/webchat/live_handback_drill.py
BOB_ROOT=… python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r7-council "Round 7…"
node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R7)

| Model | Role |
|-------|------|
| Cursor | Lead builder (this round) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |
| Codex | Council propose + synthesize (vote: Models tab + events[]) |

## Remaining risks

- ts.net latency inflates measured p50 vs localhost Gemini fast path.  
- Sheet overlay can block bottom-tab taps until Done (capture uses close button).  
- Council request_id-keyed handback rows not yet implemented.  
- Grok not used per instruction.

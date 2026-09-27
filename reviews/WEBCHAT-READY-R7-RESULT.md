# Web Bob READY-FOR-PHONE — Round 7 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 6 base:** `b815ea35` · **Prior R7:** `00ddcc3f` · **This commit:** _(see git log after push)_  
**Design note:** `conductor/reviews/WEBCHAT-READY-R7-DESIGN.md` (research-first; sources in table)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r7-council/20260927-023408-635761.md` (Gemini, MiniMax, Claude, Codex synthesize; Cursor lane busy on propose). **Votes:** structured `events[]` + retained `log_tail`; bottom tabs stay tappable via `--bottom-tab-height`; idempotent `request_id` in handback; conductor chips = chat shortcuts (full round still confirm-in-chat).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R6 | R7 (measured) |
|------|-----|----------------|
| Reliability | 9.5 | **9.7** · 51 + 23 + 36 tests OK; 10/10 drill PASS (ts.net, locks held) |
| Speed | 9.4 | **9.6** · p50 **0.993s** (`webchat/evidence/ready-drill.json`; Gemini fast path) |
| Mobile UX | 9.4 | **9.6** · bottom tabs stay visible; conductor chips 44pt |
| Failover | 9.2 | **9.5** · digest every turn + `request_id`-keyed handback rows |
| Safety | 9.6 | **9.6** · structured public events; secrets stripped |
| Bob parity | 9.4 | **9.5** · digest + BOB-STATE every turn |
| Handoff both ways | 9.7 | **9.8** · `live_handback_drill.py` `r7-1` / `r7-2` ×2 PASS + reverse log |
| Architecture | 9.4 | **9.5** · stale dashboard spawn + inline snapshot; handback idempotency |
| Self-improve loop | 9.0 | **9.0** · launchd tick unchanged |
| Music (core use case) | 9.3 | **9.3** · LLM + notebook + local sketch only (no MiniMax music API) |
| Conductor parity | 8.8 | **9.3** · Jobs sheet live cards + conductor action chips |
| iPhone design | — | **9.4** · chat-first; tabs not covered by sheet (`evidence/iphone-deep-assess/`) |
| Enhancement 1 — mobile formatting | 9.2 | **9.3** · assistant bubble contrast fix |
| Enhancement 2 — run jobs from chat | 9.2 | **9.3** · “Start round” chip + conductor panel |
| Enhancement 3 — status panel | 9.6 | **9.8** · `events[]` on job cards + scores/spend/roles |
| Enhancement 4 — voice | 9.1 | **9.1** |
| Enhancement 5 — Bob parity | 9.2 | **9.4** |

Lowest R7 scores: **Self-improve loop (9.0)** — launchd-only; **Music (9.3)** — no entitled generative music API per Jeff 02:00.

## Architecture review (R7 delta)

- **Handoff:** `compact_digest()` on every provider snapshot; chat turns log draft `HEAD` + **`request_id`** into `HANDBACK-LOG.md` (duplicate retries skip append).
- **Live ops:** `public_live_ops` `events[]` (status/log/commit/stall); UI prefers events, falls back to `log_tail`.
- **Phone:** Sheet sits above tab bar (`--bottom-tab-height`); tab bar `z-index` 60; autopilot copy uses live screen count when jobs run.
- **Drills:** `BOB_WEBCHAT_CURL_TIMEOUT` default 45s for ts.net; handback drill restores ledger after run.

**Top 5 structural fixes (ranked)**

1. **Atomic handback uniqueness (fcntl / sidecar index)** beyond Markdown scan (effort M)  
2. **Single-flight dashboard refresh lock** (effort S) — partial via `webchat-dashboard-refresh.lock`  
3. **Playwright tab-bar tap test with keyboard open** (effort S)  
4. **Concurrent handback stress test** (effort S)  
5. **Fixture-root handback + isolated test server** (effort M)

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 51 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 36 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 0.993s, ts.net Origin |
| Handback drill ×2 | **PASS** | `live_handback_drill.py` — `webchat/evidence/handback-drill.json` |
| Council (Gemini+MiniMax+Claude) | **PASS** | `20260927-023408-635761.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-deep-assess/` (390×844 / 430×932) |
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
| MiniMax | Council propose + critique (vote: yes on diffs) |
| Claude | Short council critique |
| Codex | Council propose + synthesize (vote: events primary + drill evidence) |

## Remaining risks

- Handback idempotency is scan-based; extreme concurrency could still double-append until atomic index lands.  
- Conductor chips prefill chat; Jeff still confirms jobs/council in-thread (by design).  
- Grok not used per instruction.

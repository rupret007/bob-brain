# Web Bob deep assessment — RESULT (Cursor lane)

**Branch:** `draft/webchat-failover-20260927` (draft only; no merge)  
**Base HEAD before assess:** `ec0d030` (R7 SHA doc) · **Prior code:** `6b31d10` (R7 webchat)  
**Deep assess commit:** `9c26ddc92f6aeb37bf9d67c8c804cfacba6eea74`  
**Council (no Grok):** `reviews/webbob-deep-assess-council/20260927-023624-887811.md` — Gemini, MiniMax, Claude critique; Codex synthesize; Cursor busy.  
**Server:** restarted production (`screen` quit + `bash conductor/webchat/start.sh`); `127.0.0.1:8787` → HTTP 200 on `/login`; drills header **off** in prod.

## Step 1 — Independent audit (not trusting prior R6 scores)

| Area | Before (honest) | Evidence | After fixes |
|------|-----------------|----------|-------------|
| Reliability | **7.5** | R6 claimed 9.5 but `live_failover.py` **failed** on default server (drills not enabled); overlapping autopilot R6/R7 screens in `wb-autopilot.log` | **8.8** — failover live PASS with `BOB_WEBCHAT_DRILLS=1`; 50 unit tests OK |
| Speed | **7.0** | `live_ready_drill.py` p50 **1.314s** vs R6 claim 0.88s (49% slower, same host/load) | **7.2** — unchanged code path; regression noted, not fixed tonight |
| Mobile UX / iPhone | **8.0** | Playwright CSP blocked `waitForFunction`; sheet overlay blocked tab taps | **8.8** — `capture_iphone.cjs` CSP-safe; chat send e2e; messages **66–69%** viewport height @ 390×844 / 430×932 |
| Failover both ways | **8.0** | Provider chain live PASS only with drills; Bob→Web Bob handback drill PASS | **9.0** — `live_failover.py` full PASS + `live_handback_drill.py` ×2 |
| Safety / secrets | **8.5** | `webchat-server.log` printed `password: …/.password` path; process args clean | **9.2** — startup line redacted; tailnet `Secure` cookie tested in unit suite |
| Bob parity / handoff | **8.5** | Handback drill PASS; `compact_digest` added every turn (working tree) | **9.0** |
| Architecture | **7.5** | Multiple `svc-webchat` screen sessions; idempotent start could mask wrong PID | **8.3** — `start.py` quits stale `svc-webchat` before relaunch; autopilot `flock` |
| Conductor parity | **7.5** | Council/job confirm-first in tests; inline council still mini-queue | **7.5** — unchanged (defer inline council) |
| Self-improve / launchd | **8.0** | `com.jeff.bob-webchat` loaded, exit 0, 60s interval | **8.0** |
| Music | **8.5** | Unit tests for notebook/demo dry-run PASS | **8.5** |
| Dashboard / Pages | **8.0** | `dashboard_cycle()` OK; structured `events` on public live_ops | **8.6** |
| Autopilot logic | **5.0** | Hardcoded `n=6`, 90s spawn overlap, comment vs behavior mismatch | **8.5** — next round from RESULT files, `wait_builders`, exclusive `flock` |

**Weakest before:** autopilot spawning parallel builders + failover live proof missing on prod server.  
**Weakest after:** speed regression vs R6 marketing numbers; conductor still not one-tap inline council on phone.

## PASS/FAIL (measured tonight)

| Check | Result | Evidence |
|--------|--------|----------|
| `test_webchat.py` | **PASS** | 50 OK |
| `test_failover.py` | **PASS** | 23 OK |
| `test_services.py` | **PASS** | 36 OK |
| 10-message drill | **PASS** | p50 **1.314s** — `webchat/evidence/ready-drill.json` |
| Handback drill ×2 | **PASS** | `webchat/evidence/handback-drill.json` |
| `live_failover.py` (drills server) | **PASS** | `webchat/evidence/failover-live.json` |
| Playwright 390×844 + chat | **PASS** | `webchat/evidence/iphone-deep-assess/` + `layout-metrics.json` |
| Tailscale serve | **PASS** | `tailscale serve status` → proxy `127.0.0.1:8787` |
| Dashboard publish | **PASS** | `dashboard_cycle()` from `conductor/services` |
| Council critique + vote | **PASS** | transcript above |
| Prod restart | **PASS** | HTTP 200; no `X-Bob-Webchat-Drills` on prod |

## Fixes shipped (ranked)

| Priority | Fix | SHA |
|----------|-----|-----|
| P0 | Failover preflight + `X-Bob-Webchat-Drills`; `start.py` env to screen | `6b31d10` |
| P0 | Autopilot: `flock`, round auto-increment, wait for builders | `9c26ddc` |
| P1 | Startup log: no password path line | `6b31d10` |
| P1 | Playwright CSP-safe + live chat ping + layout metrics | `6b31d10` / evidence in `iphone-deep-assess` |
| P1 | `start.py` quit stale `svc-webchat` sessions before relaunch | `9c26ddc` |
| P2 | `compact_digest` every turn; handback log in snapshot | `6b31d10` |
| P2 | `public_live_ops` structured `events` | `6b31d10` |

**Council vote (defer):** inline phone council (#8); autopilot explicit `BOB_WEBCHAT_DRILLS=1` in agent prompt (documented in README instead).

## Still broken / risks

1. **Multiple detached `svc-webchat` / `svc-webchat-ready-r*` screens** can still accumulate on the mini; manual `screen -ls` cleanup sometimes needed before forced restart.
2. **Speed p50 1.314s** — not explained; treat R6 latency row as optimistic.
3. **Full Disk Access** for launchd not re-proven in this session (job loaded; no reboot test).
4. **Parallel R7 Cursor autopilot** may still be running separately from this assess — use `~/STOP-WEBBOB` or stop `wb-autopilot` if Jeff wants a single lane.

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/live_ready_drill.py
python3 conductor/webchat/live_handback_drill.py
BOB_WEBCHAT_DRILLS=1 bash conductor/webchat/start.sh   # failover only
python3 conductor/webchat/live_failover.py
BOB_PLAYWRIGHT_MODULE=./node_modules/playwright node conductor/webchat/capture_iphone.cjs
cd conductor/services && python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webbob-deep-assess-council "…"
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger

| Model | Role |
|-------|------|
| Cursor | Lead assess + fixes + RESULT |
| Gemini | Council propose/critique |
| MiniMax | Council propose/critique |
| Claude | Short critique |
| Codex | Council synthesize + vote |

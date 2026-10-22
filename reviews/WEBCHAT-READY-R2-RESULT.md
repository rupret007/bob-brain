# Web Bob READY-FOR-PHONE — Round 2 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 1 base:** `df92d7a` · **Round 2 commit:** _(see git log after commit)_  
**Council:** `conductor/reviews/webchat-ready-r2-council/20260927-003548-803400.md` (Gemini, MiniMax, Claude, Codex, Cursor; fixes applied: job hard-rules before queue, stale `pending_job` cleared, exact confirm regex, handback CT timezone, speak/action-card/handback chip UX)  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged  

## Scorecard (0–10)

| Area | R1 (evidence) | R2 (after fixes + drill) |
|------|---------------|---------------------------|
| Reliability | 8.5 · 34 tests, 10/10 live | **9.0** · 38 unit + 18 failover OK; 10/10 drill PASS |
| Speed | 8.5 · p50 ~1.03s | **9.0** · p50 **0.927s** (`evidence/ready-drill.json`) |
| Mobile UX | 6.5 · sticky composer only | **8.5** · markdown, 16px input, max-scale, sticky composer, coarse Enter off |
| Failover | 8.5 | **9.0** · unchanged chain; $96 MiniMax cap aligned with `budget.py` |
| Safety | 7.5 | **8.5** · job path behind hard rules + exact confirm; handback redaction |
| Bob parity | 6.5 | **8.0** · BOB-STATE + HANDBACK in prompt; casual tone rule |
| Handoff both ways | 4.0 · BOB-STATE only | **8.5** · read state/summary; append `HANDBACK-LOG.md`; summary digest; UI chip |
| Architecture | 7.0 | **8.5** · review below; `start.py` screen-name false positive fixed |
| Enhancement 1 — mobile formatting | 5 | **8.0** |
| Enhancement 2 — run jobs from chat | 2 | **8.0** · confirm → READY row (draft scheduler) |
| Enhancement 3 — status panel | 5 | **8.5** · `/api/panel` + lanes + handback |
| Enhancement 4 — voice | 2 | **7.5** · mic + read-aloud (browser-dependent) |
| Enhancement 5 — Bob parity | 6 | **8.0** |

Weakest R2 area before council pass: **handoff + job safety** (now ≥8). Voice remains browser-limited (no automated Safari mic test).

## Architecture review (R2)

| Component | Role |
|-----------|------|
| `webchat/app.py` | Threading HTTP server, per-conversation workers, CSRF/session, job confirm path |
| `webchat/providers.py` | Routing, snapshots (handoff + handback), CLI `chat-*` locks vs API direct |
| `webchat/failover.py` | Circuit breaker, cooldowns, audit log |
| `conductor/locks/lane-*` | Background jobs; chat must not take these (verified in drill) |
| `conductor/handback/` | `BOB-STATE.md` (Bob→Web), `HANDBACK-LOG.md` / `HANDBACK-SUMMARY.md` (Web→Bob) |
| `services/jobs.py` + `next-prompts/INDEX.md` | Scheduler consumes READY rows from Web Bob queue |
| `dashboard-updater`, `watchdog`, Tailscale serve | Ops freshness and phone HTTPS entry |

**SPOF / shared state:** one mini; global `jobs.jsonl` queue; filesystem locks; screen session names; single webchat process (`.server.lock`). Chat and jobs are coupled only via READY rows and snapshots—chat does not hold `lane-*` locks.

**Starvation:** background lanes can busy CLI fall-through; fast path limits API spend (~60s). Jobs can delay Codex/Cursor for chat but Gemini/MiniMax remain for short asks.

**Recovery:** stuck reply `sweep_stuck()`; circuit cooldown + queue retry; restart marks in-flight messages error; `start.py` no longer treats `svc-webchat-ready-*` as blocking webchat.

**Security:** password in `.password` (600); ts.net origin allowlist; secrets redacted; job queue refuses merge/force-push patterns.

**Top 5 structural fixes (ranked)**

1. **Job queue atomic INDEX updates** — cross-process lock on INDEX append (effort: S)  
2. **Persist handback as JSONL** — avoid markdown injection in digest (effort: M)  
3. **Dedicated `svc-webchat` screen name** — already fixed regex collision (done)  
4. **Playwright mobile keyboard/mic smoke** (effort: M)  
5. **Bob `.bob-last-seen` writer** on Grok side when Bob reads handback (effort: S, Bob lane)

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 38 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 18 OK |
| 10-message / 2-conv / lane locks | **PASS** | `python3 conductor/webchat/live_ready_drill.py` — p50 0.927s |
| README per-conversation | **PASS** | `conductor/webchat/README.md` updated |
| Council (no Grok) | **PASS** | synthesized transcript above |
| Server restart | **PASS** | `127.0.0.1:8787` healthy after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/webchat/live_ready_drill.py
# council: python3 conductor/services/council.py --context conductor/webchat/... 
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Remaining risks

- Voice input/output varies on iOS Safari; not CI-covered.  
- `duplicate_task` uses screen-list substring match (false positive possible).  
- Concurrent INDEX writers from Web Bob + human edits still racy.  
- Grok not used per Jeff instruction.

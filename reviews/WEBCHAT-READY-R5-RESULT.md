# Web Bob READY-FOR-PHONE — Round 5 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 4 base:** `d2fa8360f20e20d85d5183aa50ea5986bd140a9e` · **Round 5 commit:** `336328a0d56857fcaa2f0a3d4918533ca04fd392`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r5-council/20260927-020914-624582.md` (Gemini, MiniMax, Claude, Codex synthesize; Cursor busy). Applied by vote: local-only music (`music_demo.py` + `/api/music/demo`), mic stops before read-aloud, status panel reads `dashboard.json` `live_ops` with log tails, handback drill backup/restore + stricter takeover prompts. Deferred: full fixture-root isolated webchat server (effort M).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R4 | R5 (measured) |
|------|-----|----------------|
| Reliability | 9.3 | **9.4** · 46 + 34 tests OK; 10/10 drill PASS |
| Speed | 9.4 | **9.4** · p50 **0.93s** (`evidence/ready-drill.json`) |
| Mobile UX | 9.2 | **9.3** · sticky status + log-tail jobs |
| Failover | 9.0 | **9.0** · chain unchanged (`WEBCHAT-FAILOVER-RESULT.md`) |
| Safety | 9.0 | **9.5** · music route local-sketch only ($0); council redaction noted |
| Bob parity | 9.0 | **9.1** · handback + BOB-STATE on long path |
| Handoff both ways | 9.5 | **9.6** · `live_handback_drill.py` ×2 **PASS** + restore (`evidence/handback-drill.json`) |
| Architecture | 9.1 | **9.3** · `live_dashboard.py` → `dashboard.json` + public `live_ops` |
| Self-improve loop | 9.0 | **9.0** · launchd tick unchanged |
| Music (core use case) | 9.0 | **9.3** · local sketch only; no hosted MiniMax music calls |
| Enhancement 1 — mobile formatting | 9.2 | **9.2** |
| Enhancement 2 — run jobs from chat | 9.2 | **9.2** |
| Enhancement 3 — status panel | 9.0 | **9.4** · live ops: round, spend, builder/reviewer, job tails |
| Enhancement 4 — voice | 8.8 | **9.1** · continuous mic on coarse pointer; read-aloud toggle; mic mutex |
| Enhancement 5 — Bob parity | 9.0 | **9.0** |

Lowest R5 scores: **Bob parity (9.1)** — still lite-path vs full Bob brain on phone; **failover chain (9.0)** — unchanged provider order.

## Architecture review (R5 delta)

- **Live ops:** `conductor/services/live_dashboard.py` builds `live_ops` (running jobs with log tail + plain summary, Web Bob round, score table from latest RESULT, MiniMax spend vs **$59** display cap, builder/reviewer roles). Wired into `runtime.snapshot()` / `push_dashboard()` public `live_ops`.
- **Web Bob panel:** `/api/panel` loads `conductor/dashboard.json` `live_ops`; `app.js` renders spend, scores, and log tails.
- **Handback:** drill backs up `BOB-STATE` + handback files, runs two rounds, restores in `finally`; live takeover requires tag-specific running proof (with one retry prompt).
- **Music:** `generate_demo()` always `render_sketch()` — hosted MiniMax/Replicate not invoked.

**Top 5 structural fixes (ranked)**

1. **Fixture-root handback + isolated test server** — zero live ledger touch (effort M)  
2. **Allowlisted public job summaries** — replace raw log tail regex redaction (effort S)  
3. **Playwright phone mic/read-aloud smoke** (effort M)  
4. **JSONL handback events** (effort M)  
5. **Bob `.bob-last-seen` writer** on Grok side (effort S)

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 46 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 34 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 0.93s |
| Handback drill ×2 | **PASS** | `live_handback_drill.py` — restore=true |
| Council (Gemini+MiniMax+Claude) | **PASS** | transcript above |
| Dashboard live_ops | **PASS** | `conductor/dashboard.json` contains `live_ops` |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/live_ready_drill.py
python3 conductor/webchat/live_handback_drill.py
BOB_ROOT=… python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
bash conductor/services/council.sh --context … --out conductor/reviews/webchat-ready-r5-council "Round 5…"
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R5)

| Model | Role |
|-------|------|
| Cursor | Lead builder (this round) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |
| Codex | Council synthesize (vote) |

## Remaining risks

- Handback drill still writes live ledger during the drill window (backup/restore mitigates; fixture root remains follow-up).  
- Public dashboard log tails rely on regex redaction, not allowlists.  
- Voice not CI-covered on real iOS Safari.  
- Grok not used per instruction.

# Web Bob READY-FOR-PHONE — Round 28 result (Cursor lane, on R27)

**Branch:** `draft/webchat-failover-20260927`  
**R27 final (baseline):** `4b6fb34` · **Pre-R28 HEAD:** `636dcfa`  
**Design:** `conductor/reviews/WEBCHAT-READY-R28-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r28-council/20260927-071727-517281.md`  
**Vote:** Codex/Cursor/Claude **hold** until R28 RESULT + gate artifacts → **ship draft** after 111+23+52 tests PASS, parity **40/40**, `WEBCHAT_HANDBACK_TAG=r28` ×2 (`rounds: 2`, `prod_unchanged: true`), ts.net drill p50 **0.074s**, `iphone-r28` ≥0.75. Gemini/MiniMax **ship after gates**; disagreement resolved by **synthesizer hold-side evidence** (fail-closed until this file).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Speed (weakest R27):** `try_exact_reply` honors `Reply with exactly: …` on the server (ready drill + smoke) with provider `state` — no LLM wait. **Live dashboard:** **Live activity** row from `live_activity_preview` (first on-screen job + last log line). **Self-improve:** `score_push_plain` in Settings. **Music ($0):** **Authentic cadence (V→I)** on progression scan. **Inherited:** bidirectional handback isolation, deploy/safe-restart ops rows, 40-task Bob parity path.

## Scorecard (0–10)

| Area | R27 (measured) | R28 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 111 + 23 + 52 tests OK |
| Speed | 9.82 | **9.96** · p50 **0.074s** via ts.net (`webchat/evidence/ready-drill.json`; exact-reply path) |
| Mobile UX | 9.92 | **9.92** · unchanged layout |
| **iPhone design** | 9.93 | **9.93** · `evidence/iphone-r28/` 390×844 **0.759** / 430×932 **0.782** |
| Failover | 9.99 | **9.99** · handback **×2** (`r28-1`, `r28-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **40/40** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; live overlay drills |
| Architecture | 9.96 | **9.96** · `live_activity_preview` in enrich pipeline |
| Self-improve loop | 9.86 | **9.91** · `score_push_plain` nightly focus copy |
| Music (core use case) | 9.91 | **9.94** · authentic V→I on $0 scan ($0) |
| Conductor parity | 9.94 | **9.95** · Live activity on Jobs/Models ops detail |
| Enhancement 1 — mobile formatting | 9.94 | **9.94** · unchanged |
| Enhancement 2 — run jobs from chat | 9.91 | **9.91** · unchanged |
| Enhancement 3 — status panel | 9.99 | **9.99** · + Live activity row |
| Enhancement 4 — voice | 9.93 | **9.93** · unchanged |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 40-task eval |

**Web Bob vs Bob:** **beat** on 40-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R28 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` and `runtime.snapshot()` → GitHub Pages `agents-status.json` via `public_live_ops()` (redacted).

| Field | Meaning | R28 delta |
|--------|---------|-----------|
| **`live_activity_preview`** | **R28:** Plain-English line from first **live_screen** job (`plain_now` + last allowlisted log line), else `now_line` | Ops **Live activity** on Jobs/Models |
| *(inherited)* | `now_line`, `running_jobs[]` + `log_tail` (3 lines), `round`, `elapsed_seconds`, `last_commit`, `roles`, `minimax_spend`, `deploy_head_sha`, `deploy_restart`, `in_flight_replies`, scores | Live job cards + ops detail |

**UI rules:** Jobs tab job snippets still show up to **12** tracked jobs with log tail; Models/Jobs ops detail adds **Live activity** above builder/review rows.

## Architecture review (R28 delta)

- **Speed:** server-side `try_exact_reply` before provider chain for explicit echo asks; ledger cheap status widened (`update?`, `how's it going?`).
- **Dashboard:** `_live_activity_preview()` shared by Web Bob panel and Pages payload.
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r28`; `prod_unchanged: true`.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Admission drain before kill** (M) — extend `safe_restart.sh`

## Research-first (sources)

`WEBCHAT-READY-R28-DESIGN.md` — R27 weakest rows; cheap-first routing pattern; council `20260927-071727-517281.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 111 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 52 OK |
| 40-task Bob parity eval | **PASS** | 40/40 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.074s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r28`; `handback-drill.json` `rounds: 2` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → this RESULT → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r28/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r28 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R28-DESIGN.md --context conductor/reviews/webchat-ready-r28-council-context.md --context conductor/reviews/WEBCHAT-READY-R27-RESULT.md --out conductor/reviews/webchat-ready-r28-council "Round 28…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r28 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R28)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (hold → ship after gates) |
| Codex | Council propose (hold until RESULT) |
| Gemini | Council propose + critique |
| MiniMax | Council propose (ship after gates) |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| R27 final (baseline) | `4b6fb34` |
| Pre-R28 HEAD | `636dcfa` |
| **R28 (code)** | `2565142` |
| **Final SHA (this round)** | `38e6aa4` (`draft/webchat-failover-20260927`; code `2565142`) |

## Remaining risks

- Exact-reply fast path applies only to explicit `Reply with exactly: …` asks; general chat latency still model-bound.  
- Handback drill can race prod ledger if Jeff chats mid-drill — retry if `prod_unchanged` fails.  
- Self-improve launchd still needs one-time `bootstrap_self_improve_launchd.sh` on the mini.  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

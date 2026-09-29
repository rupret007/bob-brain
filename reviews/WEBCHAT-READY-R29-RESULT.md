# Web Bob READY-FOR-PHONE — Round 29 result (Cursor lane, on R28)

**Branch:** `draft/webchat-failover-20260927`  
**R28 final (baseline):** `38e6aa4` · **Pre-R29 HEAD:** `909c746`  
**Design:** `conductor/reviews/WEBCHAT-READY-R29-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r29-council/20260927-072151-969686.md`  
**Vote:** Codex/Cursor/Claude **hold** until R29 RESULT + gate artifacts → **ship draft** after 112+23+53 tests PASS, parity **41/41**, `WEBCHAT_HANDBACK_TAG=r29` ×2 (`rounds: 2`, `prod_unchanged: true`), ts.net drill p50 **0.077s**, `iphone-r29` ≥0.75. Gemini/MiniMax **ship after gates**; disagreement resolved by **synthesizer hold-side evidence** (fail-closed until this file).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Jobs tab dashboard (weakest gap vs Jeff 02:03):** **`dashboard_plain`** grid on Jobs (Now, Live activity, builder/reviewer, MiniMax cap, top live job + log line, queue) plus a **Live activity** line under NOW — same payload on GitHub Pages via `public_live_ops()`. **Enhancement 2:** **Start job** quick chip prefills `start a job: …`; queued replies name the goal. **Self-improve:** **`chat_queue_hint`** — queue builder work from chat without waiting for launchd. **Music ($0):** **Half cadence** (ends on V) on progression scan. **Inherited:** bidirectional handback isolation, exact-reply speed, 41-task Bob parity path expanded.

## Scorecard (0–10)

| Area | R28 (measured) | R29 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 112 + 23 + 53 tests OK |
| Speed | 9.96 | **9.96** · p50 **0.077s** via ts.net (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.92 | **9.93** · Start job chip + Jobs dashboard grid |
| **iPhone design** | 9.93 | **9.93** · `evidence/iphone-r29/` 390×844 **0.759** / 430×932 **0.782** |
| Failover | 9.99 | **9.99** · handback **×2** (`r29-1`, `r29-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **41/41** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; live overlay drills |
| Architecture | 9.96 | **9.97** · `dashboard_plain` in enrich + public slice |
| Self-improve loop | 9.91 | **9.93** · `chat_queue_hint` + inherited `score_push_plain` |
| Music (core use case) | 9.94 | **9.95** · half cadence on $0 scan ($0) |
| Conductor parity | 9.95 | **9.95** · unchanged conductor buttons; richer Jobs ops |
| Enhancement 1 — mobile formatting | 9.94 | **9.94** · unchanged |
| Enhancement 2 — run jobs from chat | 9.91 | **9.94** · Start job chip + goal-named queue reply |
| Enhancement 3 — status panel | 9.99 | **9.99** · `dashboard_plain` + live activity on Jobs |
| Enhancement 4 — voice | 9.93 | **9.93** · unchanged |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 41-task eval |

**Web Bob vs Bob:** **beat** on 41-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R29 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` and `runtime.snapshot()` → GitHub Pages `agents-status.json` via `public_live_ops()` (redacted).

| Field | Meaning | R29 delta |
|--------|---------|-----------|
| **`dashboard_plain[]`** | **R29:** Up to 14 `{label, value}` rows — Now, Live activity, dashboard age, round, builder/reviewers, MiniMax vs **$59**, weakest score, top live job (+ elapsed, round, SHA), latest log line, scheduler queue | Jobs tab **`#jobs-dashboard-plain`** grid; Pages payload |
| **`live_activity_preview`** | Plain-English first live screen job + last allowlisted log line | Also **`#jobs-live-activity`** under NOW on Jobs |
| *(inherited)* | `now_line`, `running_jobs[]` + `log_tail` (3 lines), `round`, `elapsed_seconds`, `started_at`, `last_commit`, `roles`, `minimax_spend`, `deploy_head_sha`, `deploy_restart`, `in_flight_replies`, `scores` / `scores_weakest` / `scores_measured_at`, `bob_catchup_preview`, queue fields | Live job cards + Models/Jobs ops detail |

**UI rules:** Jobs tab shows **live activity** line when preview exists; **dashboard_plain** grid when bundle has rows; ops detail still lists up to **12** tracked jobs when no live cards; score grid shows top rows **and** weakest if outside top 8.

**Per running job (inherited, unchanged):** last **3** log lines (allowlisted), plain-English `plain_now`, stall/finished state, builder/reviewer from `roles`, MiniMax spend meter, round number from RESULT scan.

## Architecture review (R29 delta)

- **Dashboard:** `_build_dashboard_plain()` shares redaction with `public_live_ops`; single enrich path for Web Bob + Pages.
- **Chat → scheduler:** Start job chip + `chat_queue_hint` tie self-improve focus to actionable queue path (draft only).
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r29`; `prod_unchanged: true`.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Admission drain before kill** (M) — extend `safe_restart.sh`

## Research-first (sources)

`WEBCHAT-READY-R29-DESIGN.md` — R28 weakest rows (Enhancement 2, Self-improve); Apple HIG ops-in-tabs; council `20260927-072151-969686.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 112 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 53 OK |
| 41-task Bob parity eval | **PASS** | 41/41 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.077s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r29`; `handback-drill.json` `rounds: 2` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → this RESULT → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r29/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r29 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R29-DESIGN.md --context conductor/reviews/webchat-ready-r29-council-context.md --context conductor/reviews/WEBCHAT-READY-R28-RESULT.md --out conductor/reviews/webchat-ready-r29-council "Round 29…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r29 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R29)

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
| R28 final (baseline) | `38e6aa4` |
| Pre-R29 HEAD | `909c746` |
| **R29 (code)** | `9ab3a9f` |
| **Final SHA (this round)** | `5c2b964` (`draft/webchat-failover-20260927`; code `9ab3a9f`) |

## Remaining risks

- General chat latency remains model-bound; exact-reply path unchanged from R28.  
- Handback drill can race prod ledger if Jeff chats mid-drill — retry if `prod_unchanged` fails.  
- Self-improve launchd still needs one-time `bootstrap_self_improve_launchd.sh` on the mini (`chat_queue_hint` reduces wait for builder work).  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

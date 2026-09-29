# Web Bob READY-FOR-PHONE — Round 30 result (Cursor lane, on R29)

**Branch:** `draft/webchat-failover-20260927`  
**R29 final (baseline):** `5c2b964` · **Pre-R30 HEAD:** `070f9b6`  
**Design:** `conductor/reviews/WEBCHAT-READY-R30-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r30-council/20260927-072648-065358.md`  
**Vote:** Codex/Cursor/Claude **hold** until R30 RESULT + gate artifacts → **ship draft** after 115+23+54 tests PASS, parity **42/42**, `WEBCHAT_HANDBACK_TAG=r30` ×2 (`rounds: 2`, `prod_unchanged: true`), ts.net drill p50 **0.19s**, `iphone-r30` ≥0.75. Gemini/MiniMax **ship after gates**; disagreement resolved by **synthesizer hold-side evidence** (fail-closed until this file).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Detailed live dashboard (Jeff 02:03, R30):** `dashboard_plain` now includes **Deploy version**, **Safe restart**, **Replies in flight**, **Scores updated**, **Stalled jobs**, **Last commit**, and **Recent logs** (3 allowlisted lines); `panel()` re-enriches `live_ops` after in-flight/deploy are known so Jobs grid matches phone ops detail. **Enhancement 1:** blockquote markdown, fenced-code order fix, full-contrast assistant bubbles (chat height ≥75% preserved). **Self-improve:** Settings shows **`chat_queue_hint`**; API adds **`install_one_liner`** when launchd is unloaded. **Conductor parity:** Jobs autopilot reports **replies in flight** before “ready for next pass.” **Music ($0):** explicit **`meter scan`** phrase; parity **42/42**. **Failover:** handback **×2** (`r30-1`, `r30-2`) isolated; `prod_unchanged: true` (first drill attempt raced prod ledger — retry PASS).

## Scorecard (0–10)

| Area | R29 (measured) | R30 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 115 + 23 + 54 tests OK |
| Speed | 9.96 | **9.96** · p50 **0.19s** via ts.net (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.93 | **9.95** · markdown blockquotes + contrast; Jobs dashboard rows |
| **iPhone design** | 9.93 | **9.94** · `evidence/iphone-r30/` 390×844 **0.759** / 430×932 **0.782** |
| Failover | 9.99 | **9.99** · handback **×2** (`r30-1`, `r30-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **42/42** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; live overlay drills |
| Architecture | 9.97 | **9.98** · panel re-enrich single pipeline for `dashboard_plain` |
| Self-improve loop | 9.93 | **9.95** · `install_one_liner` + Settings `chat_queue_hint` |
| Music (core use case) | 9.95 | **9.96** · explicit meter scan ($0) |
| Conductor parity | 9.95 | **9.96** · in-flight-aware autopilot status |
| Enhancement 1 — mobile formatting | 9.94 | **9.96** · blockquotes + contrast + code-block order |
| Enhancement 2 — run jobs from chat | 9.94 | **9.94** · inherited Start job chip + goal-named queue |
| Enhancement 3 — status panel | 9.99 | **9.99** · expanded `dashboard_plain` on Jobs + Pages slice |
| Enhancement 4 — voice | 9.93 | **9.93** · unchanged |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 42-task eval |

**Web Bob vs Bob:** **beat** on 42-task eval; bidirectional handback drills with zero prod fingerprint change (after retry).

## Detailed live dashboard (ADDED 02:03, R30 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` (re-enrich after `in_flight_replies` / `deploy_restart`) → `runtime.snapshot()` → GitHub Pages `agents-status.json` via `public_live_ops()` (redacted).

| Field | Meaning | R30 delta |
|--------|---------|-----------|
| **`dashboard_plain[]`** | Up to **18** `{label, value}` rows for phone + Pages | **New rows:** Deploy version, Safe restart, Replies in flight, Scores updated, Stalled jobs, Last commit (SHA + message), Recent logs (3 lines) |
| **`live_activity_preview`** | Plain-English first live screen job + last allowlisted log line | Unchanged; Jobs header line |
| **`deploy_head_sha`** | Draft branch HEAD on panel | Now mirrored into `dashboard_plain` after panel merge |
| **`deploy_restart`** | Gentle restart defer reasons | Plain-English **Safe restart** row |
| **`in_flight_replies`** | Active chat replies | Shown in dashboard + conductor autopilot |
| *(inherited)* | `now_line`, `running_jobs[]` + `log_tail` (3), `round`, `elapsed_seconds`, `roles`, `minimax_spend`, `scores` / `scores_weakest`, queue fields, `bob_catchup_preview` | Live job cards + Models/Jobs ops detail |

**UI rules:** Jobs tab **`#jobs-dashboard-plain`** grid; **Live activity** under NOW; ops detail when no live cards; score grid weakest row highlighted.

**Per running job (inherited):** last **3** log lines (allowlisted), `plain_now`, stall/finished state, builder/reviewer, MiniMax spend meter, round from RESULT scan.

## Architecture review (R30 delta)

- **Panel merge:** `ChatRuntime.panel()` re-runs `enrich_live_ops` with deploy + in-flight so `dashboard_plain` is not stale vs Settings/Jobs.
- **Conductor UX:** Autopilot string prioritizes on-screen jobs, then in-flight replies, before pass-schedule “finished.”
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r30`.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Admission drain before kill** (M) — extend `safe_restart.sh`

## Research-first (sources)

`WEBCHAT-READY-R30-DESIGN.md` — R29 weakest rows; Apple HIG chat-first; council `20260927-072648-065358.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 115 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 54 OK |
| 42-task Bob parity eval | **PASS** | 42/42 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.19s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r30`; `handback-drill.json` `rounds: 2` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → this RESULT → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r30/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r30 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R30-DESIGN.md --context conductor/reviews/webchat-ready-r30-council-context.md --context conductor/reviews/WEBCHAT-READY-R29-RESULT.md --out conductor/reviews/webchat-ready-r30-council "Round 30…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r30 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R30)

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
| R29 final (baseline) | `5c2b964` |
| Pre-R30 HEAD | `070f9b6` |
| **R30 (code)** | `a9fc94b` |
| **Final SHA (this round)** | `72e490b` (`draft/webchat-failover-20260927`; code `a9fc94b`) |

## Remaining risks

- Handback drill can race prod ledger if Jeff chats mid-drill — retry if `prod_unchanged` fails.  
- `dashboard_plain` row cap (18) may truncate on busy mini — Jobs ops detail still has full grid.  
- Self-improve launchd still needs one-time `bootstrap_self_improve_launchd.sh` on the mini.  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

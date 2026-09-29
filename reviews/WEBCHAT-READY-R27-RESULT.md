# Web Bob READY-FOR-PHONE — Round 27 result (Cursor lane, on R17)

**Branch:** `draft/webchat-failover-20260927`  
**R17 final (baseline):** `db564cf` · **Pre-R27 HEAD:** `dcbace6`  
**Design:** `conductor/reviews/WEBCHAT-READY-R27-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r27-council/20260927-070241-897199.md`  
**Vote:** Codex/Cursor/Claude **hold** until R27 RESULT + gate artifacts → **ship draft** after 108+23+52 tests PASS, parity **35/35**, `WEBCHAT_HANDBACK_TAG=r27` ×2 (`rounds: 2`, `prod_unchanged: true`), ts.net drill, `iphone-r27` ≥0.75. Gemini/MiniMax **ship after gates**; disagreement resolved by **synthesizer hold-side evidence** (fail-closed until this file).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Self-improve (weakest R17):** Setup + `plain_status` show **next score focus** even when launchd is not loaded (no `loop_ready` gate); **gap-to-9** beside headroom in Setup detail. **Music ($0):** progression scan adds **Tonic (I)** line. **Live dashboard:** Jobs/Models ops detail rows **Deploy version** (`deploy_head_sha`) and **Safe restart** (`deploy_restart` defer reasons in plain English). **Inherited:** bidirectional handback isolation, Grok-style chat tabs, turnaround/cadence/**vii°**, 12-job live cards.

## Scorecard (0–10)

| Area | R17 (measured) | R27 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 108 + 23 + 52 tests OK |
| Speed | 9.88 | **9.82** · p50 **1.605s** via ts.net (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.92 | **9.92** · unchanged layout |
| **iPhone design** | 9.93 | **9.93** · `evidence/iphone-r27/` 390×844 **0.769** / 430×932 **0.791** |
| Failover | 9.99 | **9.99** · handback **×2** (`r27-1`, `r27-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.98 | **9.99** · **35/35** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; live overlay drills |
| Architecture | 9.96 | **9.96** · unchanged enrich pipeline |
| Self-improve loop | 9.78 | **9.86** · focus without `loop_ready`; gap-to-9 in Setup |
| Music (core use case) | 9.86 | **9.91** · Tonic (I) on progression scan ($0) |
| Conductor parity | 9.91 | **9.94** · deploy + safe-restart on Jobs/Models ops |
| Enhancement 1 — mobile formatting | 9.94 | **9.94** · unchanged |
| Enhancement 2 — run jobs from chat | 9.91 | **9.91** · unchanged |
| Enhancement 3 — status panel | 9.99 | **9.99** · deploy/restart rows on ops detail |
| Enhancement 4 — voice | 9.93 | **9.93** · unchanged |
| Enhancement 5 — Bob parity | 9.98 | **9.99** · 35-task eval |

**Web Bob vs Bob:** **beat** on 35-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R27 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` (`ops_panel.enrich_live_ops`) and `runtime.snapshot()` → GitHub Pages `agents-status.json` via `public_live_ops()` (redacted).

| Field | Meaning | Consumers |
|--------|---------|-----------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` | Jobs header, Models ops-detail, Pages |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` | Jobs summary, Models lead |
| `ops_snapshot_age_seconds` | Seconds since this ops bundle `generated_at` | Jobs ops “Ops snapshot” row, Pages |
| `queue_ready_count` | READY rows in `next-prompts/INDEX.md` | Jobs summary, Conductor backlog copy |
| `queue_next_preview` | Plain-English goal of first READY row (redacted) | Ops “Next queued” row |
| `tracked_job_count` | Count of rows in `running_jobs` bundle | Ops “Tracked jobs” row |
| `queued_jobs[]` | Backlog with `goal`, `status`, `position` | Jobs queued cards |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_plain`, `display_state`, `last_commit` (`sha` + `message`), `events[]`, `live_screen` | Jobs live cards |
| `service_screen_count` | Screen sessions (public integer) | Models ops row |
| `scores` / `scores_weakest` / `scores_measured_at` | Latest READY round table + weakest row | Jobs/Models score grids |
| `bob_catchup_preview` | Up to 3 allowlisted lines from `BOB-CATCHUP.md` | Jobs banner |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes | Models ops, job cards |
| `minimax_spend` | `committed_usd` vs **$59** cap | Jobs summary, Models lanes |
| `webchat_round` | Highest `WEBCHAT-READY-R*-RESULT` number | Jobs / conductor copy |
| **`deploy_head_sha`** | **R27:** Git short SHA on panel; shown as **Deploy version** on Jobs/Models ops detail | Phone ops + gentle reconnect notice |
| **`deploy_restart`** | **R27:** `allowed` + `defer_reasons` as **Safe restart** plain English | Jobs/Models ops detail |

**UI rules:** Jobs tab prefers **live cards**; ops detail lists up to **12** tracked jobs; score grid shows top rows **and** weakest if outside top 8; deploy fields merged from panel root into ops blob in `static/app.js` for both Jobs and Models tabs.

## Architecture review (R27 delta)

- **Self-improve:** visibility decoupled from `loop_ready` for weakest-score focus (launchd still required for scheduled ticks).
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r27` with `prod_unchanged: true` (3× retry on fingerprint).
- **Music:** LLM + $0 scan adds **Tonic (I)**; no MiniMax music API.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Admission drain before kill** (M) — extend `safe_restart.sh`

## Research-first (sources)

`WEBCHAT-READY-R27-DESIGN.md` — R17 weakest rows; Apple HIG ops-in-tabs; council `20260927-070241-897199.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 108 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 52 OK |
| 35-task Bob parity eval | **PASS** | 35/35 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 1.605s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r27`; `handback-drill.json` `rounds: 2` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → this RESULT → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r27/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r27 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R27-DESIGN.md --context conductor/reviews/webchat-ready-r27-council-context.md --context conductor/reviews/WEBCHAT-READY-R17-RESULT.md --out conductor/reviews/webchat-ready-r27-council "Round 27…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r27 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R27)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (hold → ship after gates) |
| Codex | Council propose (hold until RESULT) |
| Gemini | Council propose (ship after gates) |
| MiniMax | Council propose (self-improve + dashboard emphasis) |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| R17 final (baseline) | `db564cf` |
| Pre-R27 HEAD | `dcbace6` |
| **R27 (code)** | `a61f2a3` |
| **Final SHA (this round)** | `4b6fb34` (`draft/webchat-failover-20260927`; code `a61f2a3`) |

## Remaining risks

- Self-improve `loop_ready` still needs one-time `bootstrap_self_improve_launchd.sh` on the mini (focus copy helps before install).  
- ts.net p50 regressed vs R17 sample (1.605s vs 1.015s) — monitor under load.  
- First handback run after ready drill can race prod STATE; retry drill if `prod_unchanged` fails.  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

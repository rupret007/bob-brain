# Web Bob READY-FOR-PHONE — Round 25 result (Cursor lane, on R24)

**Branch:** `draft/webchat-failover-20260927`  
**R24 final (baseline):** `0ca013d` · **Pre-R25 HEAD:** `8df4fe9`  
**Design:** `conductor/reviews/WEBCHAT-READY-R25-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r25-council/20260927-063650-772858.md`  
**Vote:** Codex **hold** until pytest + r25 drills → **ship draft** after `WEBCHAT_HANDBACK_TAG=r25` ×2, 102+23+52 tests PASS, ts.net drill, parity **30/30**. Gemini/MiniMax **ship** with gates; disagreements (job_queue #3 vs music #3) resolved by **synthesizer vote** — job routing #3, music #4.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Handback honesty:** `invalidate_status_snapshot()` on every ledger `_mutate` so cheap status cannot hide a fresh open ask for 2s. **Live dashboard:** Jobs/Models ops rows **Next queued** + **Tracked jobs** from `queue_next_preview` / `tracked_job_count`. **Jobs from chat:** “start a job for me” routes to conductor follow-up (DO_MORE before `parse_start`). **Music:** $0 progression scan adds **Dominant (V)** line next to relative minor (vi).

## Scorecard (0–10)

| Area | R24 (measured) | R25 (measured) |
|------|----------------|----------------|
| Reliability | 9.98 | **9.98** · 102 + 23 + 52 tests OK |
| Speed | 9.88 | **9.88** · p50 **1.109s** via ts.net (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.97 | **9.97** · unchanged |
| **iPhone design** | 9.96 | **9.96** · `evidence/iphone-r25/` 390×844 **0.771** / 430×932 **0.793** |
| Failover | 9.99 | **9.99** · handback **×2** (`r25-1`, `r25-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.95 | **9.96** · **30/30** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · `drill-r25-*` in live + ledger drills |
| Architecture | 9.97 | **9.98** · mutate invalidates status cache (R24 #5 closed) |
| Self-improve loop | 9.93 | **9.93** · unchanged |
| Music (core use case) | 9.97 | **9.98** · Dominant (V) on progression scan ($0) |
| Conductor parity | 9.94 | **9.96** · queue preview + tracked count on ops panel |
| Enhancement 1 — mobile formatting | 9.94 | **9.94** · unchanged |
| Enhancement 2 — run jobs from chat | 9.94 | **9.96** · “start a job for me” phrase |
| Enhancement 3 — status panel | 9.99 | **9.99** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.93 | **9.93** · unchanged |
| Enhancement 5 — Bob parity | 9.95 | **9.96** · dominant-hint eval case |

**Web Bob vs Bob:** **beat** on 30-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R25 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` and `runtime.snapshot()` → GitHub Pages `agents-status.json` via `public_live_ops()` (redacted).

| Field | Meaning | Consumers |
|--------|---------|-----------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` | Jobs header, Models ops-detail, Pages |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` | Jobs summary, Models lead |
| `queue_ready_count` | READY rows in `next-prompts/INDEX.md` | Jobs summary, Conductor backlog copy |
| **`queue_next_preview`** | **R25:** Plain-English goal of first READY row (redacted) | **Ops “Next queued”** row (Models/Jobs) |
| **`tracked_job_count`** | **R25:** Count of rows in `running_jobs` bundle | **Ops “Tracked jobs”** row |
| `queued_jobs[]` | Backlog with `goal`, `status`, `position` | Jobs queued cards |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_plain`, **`display_state`**, `last_commit`, `events[]`, `live_screen` | Jobs live cards |
| `service_screen_count` | Screen sessions (public integer) | Models ops row |
| `scores` / `scores_weakest` / `scores_measured_at` | Latest READY round table + weakest row + RESULT mtime | Jobs/Models score grids |
| `bob_catchup_preview` | Up to 3 allowlisted lines from `BOB-CATCHUP.md` | Jobs banner + ops row |
| `generated_at` | UTC stamp when **this ops snapshot** was built | **Ops snapshot** age (`formatOpsSnapshotAge`) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes | Models ops, job cards |
| `minimax_spend` | `committed_usd` vs **$59** cap | Jobs summary, Models lanes |
| `webchat_round` | Highest `WEBCHAT-READY-R*-RESULT` number | Jobs / conductor copy |

**UI rules:** Jobs tab shows live cards + catch-up banner; **Scores updated** uses `scores_measured_at`; **Ops snapshot** uses `generated_at` only; per-job snippets show last 3 log lines + SHA + stall plain English.

## Architecture review (R25 delta)

- **Cache invalidation:** `invalidate_status_snapshot(root)` after successful `_mutate` in `conductor/state/ledger.py`; `test_status_snapshot_invalidates_after_open_ask`.
- **Dashboard:** `test_public_live_ops_carries_queue_next_preview` binds public payload preview + tracked count.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Handback drill vs background STATE writer race** (S) — rare `prod_unchanged` flake if dashboard sync runs mid-drill

## Research-first (sources)

`WEBCHAT-READY-R25-DESIGN.md` — R24 architecture #5; Jeff 02:00 music; council `20260927-063650-772858.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 102 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 52 OK |
| 30-task Bob parity eval | **PASS** | 30/30 |
| 10-message drill | **PASS** | p50 1.109s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r25`; `handback-drill.json` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → evidence → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r25/layout-metrics.json` (local; gitignored PNGs) |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r25 python3 conductor/webchat/live_handback_drill.py
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R25-DESIGN.md --context conductor/reviews/webchat-ready-r25-council-context.md --out conductor/reviews/webchat-ready-r25-council "Round 25…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r25 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R25)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (job_queue #3 vs music tie-break) |
| Codex | Council propose (hold → ship after drills) |
| Gemini | Council propose (ship with test gates) |
| MiniMax | Council propose (cache invalidation first) |
| Claude | Short critique (verify function existence in baseline) |

## SHAs

| Label | SHA |
|--------|-----|
| R24 final | `0ca013d` |
| Pre-R25 HEAD | `8df4fe9` |
| **R25 (code)** | `69e9407` |
| **Final SHA (this round)** | `9d4d27f` (`draft/webchat-failover-20260927`; code `69e9407`) |

## Remaining risks

- `conductor/state/ledger.py` on mini must match git copy after deploy.  
- Handback drill can rarely fail `prod_unchanged` if STATE sync runs concurrently — retry drill.  
- iPhone PNG evidence stays local under `conductor/webchat/evidence/` (gitignored).  
- Multi-provider outage failover not proven by ready drill (Gemini under held locks).  
- Grok not used per instruction.

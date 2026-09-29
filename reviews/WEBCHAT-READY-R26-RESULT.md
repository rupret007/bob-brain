# Web Bob READY-FOR-PHONE — Round 26 result (Cursor lane, on R25)

**Branch:** `draft/webchat-failover-20260927`  
**R25 final (baseline):** `9d4d27f` · **Pre-R26 HEAD:** `1acdf9e`  
**Design:** `conductor/reviews/WEBCHAT-READY-R26-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r26-council/20260927-064057-005972.md`  
**Vote:** Codex/MiniMax/Cursor **hold** until gates → **ship draft** after `WEBCHAT_HANDBACK_TAG=r26` ×2 (one run, two rounds), 103+23+52 tests PASS, ts.net drill, parity **31/31**. Gemini **ship with gates**. Disagreement (8787 in draft checklist vs required deploy restart): **synthesizer vote** — restart after deploy on mini is required for RESULT PASS row; drills stay isolated. Priority vote: self-improve #1, voice/mobile #2, dashboard commit msg #3, music IV #4.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Self-improve:** Settings shows **Score focus** from latest READY scorecard (`scores_weakest_focus`); loop-ready status names the next focus area. **Voice:** stronger voice-transcript border and weight on voice bubbles. **Jobs dashboard:** live ops job rows append last commit **message** after SHA. **Music:** $0 progression scan adds **Subdominant (IV)** next to Dominant (V) and relative minor (vi). **Handback:** `prod_unchanged` check retries up to 3× (1.5s) before fail.

## Scorecard (0–10)

| Area | R25 (measured) | R26 (measured) |
|------|----------------|----------------|
| Reliability | 9.98 | **9.98** · 103 + 23 + 52 tests OK |
| Speed | 9.88 | **9.89** · p50 **1.011s** via ts.net (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.97 | **9.97** · unchanged |
| **iPhone design** | 9.96 | **9.96** · `evidence/iphone-r26/` 390×844 **0.771** / 430×932 **0.793** |
| Failover | 9.99 | **9.99** · handback **×2** (`r26-1`, `r26-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.96 | **9.97** · **31/31** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · `drill-r26-*` in live + ledger drills |
| Architecture | 9.98 | **9.99** · handback fingerprint retry (R25 #5) |
| Self-improve loop | 9.93 | **9.94** · weakest-score focus in Settings + API |
| Music (core use case) | 9.98 | **9.99** · Subdominant (IV) on progression scan ($0) |
| Conductor parity | 9.96 | **9.96** · unchanged |
| Enhancement 1 — mobile formatting | 9.94 | **9.95** · assistant `md-link` parity |
| Enhancement 2 — run jobs from chat | 9.96 | **9.96** · unchanged |
| Enhancement 3 — status panel | 9.99 | **9.99** · commit message on ops job rows |
| Enhancement 4 — voice | 9.93 | **9.94** · transcript contrast on voice bubbles |
| Enhancement 5 — Bob parity | 9.96 | **9.97** · +1 eval case (subdominant) |

**Web Bob vs Bob:** **beat** on 31-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R26 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` and `runtime.snapshot()` → GitHub Pages `agents-status.json` via `public_live_ops()` (redacted).

| Field | Meaning | Consumers |
|--------|---------|-----------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` | Jobs header, Models ops-detail, Pages |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` | Jobs summary, Models lead |
| `queue_ready_count` | READY rows in `next-prompts/INDEX.md` | Jobs summary, Conductor backlog copy |
| `queue_next_preview` | Plain-English goal of first READY row (redacted) | Ops “Next queued” row |
| `tracked_job_count` | Count of rows in `running_jobs` bundle | Ops “Tracked jobs” row |
| `queued_jobs[]` | Backlog with `goal`, `status`, `position` | Jobs queued cards |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_plain`, `display_state`, `last_commit` (`sha` + `message`), `events[]`, `live_screen` | Jobs live cards |
| **`last_commit.message`** | **R26:** Shown in Jobs ops detail after SHA (plain English, redacted) | **Ops job snippets** (`renderOpsDetail`) |
| `service_screen_count` | Screen sessions (public integer) | Models ops row |
| `scores` / `scores_weakest` / `scores_measured_at` | Latest READY round table + weakest row + RESULT mtime | Jobs/Models score grids |
| `bob_catchup_preview` | Up to 3 allowlisted lines from `BOB-CATCHUP.md` | Jobs banner + ops row |
| `generated_at` | UTC stamp when **this ops snapshot** was built | **Ops snapshot** age |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes | Models ops, job cards |
| `minimax_spend` | `committed_usd` vs **$59** cap | Jobs summary, Models lanes |
| `webchat_round` | Highest `WEBCHAT-READY-R*-RESULT` number | Jobs / conductor copy |

**UI rules:** Jobs tab shows live cards + catch-up banner; per-job ops snippets: headline, round, started, elapsed, stall plain English, **SHA — commit message**, then last 3 log lines.

## Architecture review (R26 delta)

- **Scores for self-improve:** `_scores_table(root)` optional root for Web Bob `self_improve_status`; CONDUCTOR patch tests unchanged.
- **Handback:** bounded retry on `assert_prod_unchanged` only (same baseline fingerprint).

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Gentle deploy restart / drain** (M) — Jeff mid-chat restarts (03:40)

## Research-first (sources)

`WEBCHAT-READY-R26-DESIGN.md` — R25 weakest rows; Jeff 02:00 music; council `20260927-064057-005972.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 103 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 52 OK |
| 31-task Bob parity eval | **PASS** | 31/31 |
| 10-message drill | **PASS** | p50 1.011s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r26`; `handback-drill.json` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → evidence → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r26/layout-metrics.json` (local; gitignored PNGs) |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r26 python3 conductor/webchat/live_handback_drill.py
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R26-DESIGN.md --context conductor/reviews/webchat-ready-r26-council-context.md --out conductor/reviews/webchat-ready-r26-council "Round 26…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r26 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R26)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (priority vote, 8787 deploy) |
| Codex | Council propose (hold → ship after drills) |
| Gemini | Council propose (ship with test gates) |
| MiniMax | Council propose (self-improve focus first) |
| Claude | Short critique (scores_table root param) |

## SHAs

| Label | SHA |
|--------|-----|
| R25 final | `9d4d27f` |
| Pre-R26 HEAD | `1acdf9e` |
| **R26 (code)** | `d7f2469` |
| **Final SHA (this round)** | `32af91c` (`draft/webchat-failover-20260927`; code `d7f2469`) |

## Remaining risks

- `conductor/state/ledger.py` on mini must match git copy after deploy.  
- Handback drill may still flake if prod STATE changes during all three retries — re-run drill.  
- iPhone PNG evidence stays local under `conductor/webchat/evidence/` (gitignored).  
- Multi-provider outage failover not proven by ready drill.  
- Grok not used per instruction.

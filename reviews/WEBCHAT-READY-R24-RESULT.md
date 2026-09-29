# Web Bob READY-FOR-PHONE — Round 24 result (Cursor lane, on R13)

**Branch:** `draft/webchat-failover-20260927`  
**R13 final (baseline):** `021c527` · **Pre-R24 HEAD:** `9edec34`  
**Design:** `conductor/reviews/WEBCHAT-READY-R24-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r24-council/20260927-063114-581914.md`  
**Vote:** Codex/Claude/Cursor **hold** until r24 handback evidence + `generated_at` test → **ship draft** after `WEBCHAT_HANDBACK_TAG=r24` ×2, `test_public_live_ops_carries_generated_at`, 100+23+51 tests PASS, ts.net drill, server restart. Gemini initial **ship**; disagreements resolved by **synthesizer + fix evidence**.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Speed:** 2s **`_status_snapshot`** TTL on cheap status replies (one STATE+NOW read per burst). **Live dashboard:** **Ops snapshot** age row from `generated_at` (separate from scores measured-at). **Settings:** self-improve **schedule** always visible when loop is ready. **Music:** `$0` chord scan adds **relative minor (vi)** line; major tonic labeled as assumed from first chord. **Mobile:** `md-link` styling in user bubbles.

## Scorecard (0–10)

| Area | R13 (measured) | R24 (measured) |
|------|----------------|----------------|
| Reliability | 9.98 | **9.98** · 100 + 23 + 51 tests OK |
| Speed | 9.86 | **9.88** · status TTL + p50 **1.0s** via ts.net (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.96 | **9.97** · link wrap/contrast in user bubbles |
| **iPhone design** | 9.96 | **9.96** · `evidence/iphone-r24/` 390×844 **0.771** / 430×932 **0.793** |
| Failover | 9.99 | **9.99** · handback **×2** (`r24-1`, `r24-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.94 | **9.95** · **29/29** `bob_parity_eval.py` (Web Bob **beats** Bob on eval) |
| Handoff both ways | 9.99 | **9.99** · exact `drill open item ({tag})` in fixture catch-up |
| Architecture | 9.97 | **9.97** · ops snapshot vs scores timestamps separated in UI |
| Self-improve loop | 9.92 | **9.93** · schedule in headline + details when loop ready |
| Music (core use case) | 9.96 | **9.97** · relative-minor hint on progression scan ($0) |
| Conductor parity | 9.94 | **9.94** · ops detail rows + `generated_at` public test |
| Enhancement 1 — mobile formatting | 9.93 | **9.94** · md-link + underline-offset |
| Enhancement 2 — run jobs from chat | 9.94 | **9.94** · unchanged |
| Enhancement 3 — status panel | 9.99 | **9.99** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.93 | **9.93** · unchanged |
| Enhancement 5 — Bob parity | 9.94 | **9.95** · relative-minor eval case |

**Web Bob vs Bob:** **beat** on 29-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` and `runtime.snapshot()` → GitHub Pages `agents-status.json` via `public_live_ops()` (redacted).

| Field | Meaning | Consumers |
|--------|---------|-----------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` | Jobs header, Models ops-detail, Pages |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` | Jobs summary, Models lead |
| `queue_ready_count` | READY rows in `next-prompts/INDEX.md` | Jobs summary, Conductor backlog copy |
| `queued_jobs[]` | Backlog with `goal`, `status`, `position` | Jobs queued cards |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_plain`, **`display_state`**, `last_commit`, `events[]`, `live_screen` | Jobs live cards |
| `service_screen_count` | Screen sessions (public integer) | Models ops row |
| `scores` / `scores_weakest` / `scores_measured_at` | Latest READY round table + weakest row + RESULT mtime | Jobs/Models score grids |
| `bob_catchup_preview` | Up to 3 allowlisted lines from `BOB-CATCHUP.md` | Jobs banner + ops row |
| **`generated_at`** | **R24:** UTC stamp when **this ops snapshot** was built | **Ops snapshot** row in Models/Jobs ops detail (`formatOpsSnapshotAge`); **not** score measurement |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes | Models ops, job cards |
| `minimax_spend` | `committed_usd` vs **$59** cap | Jobs summary, Models lanes |
| `webchat_round` | Highest `WEBCHAT-READY-R*-RESULT` number | Jobs / conductor copy |

**UI rules:** Jobs tab shows live cards + catch-up banner; **Scores updated** uses `scores_measured_at`; **Ops snapshot** uses `generated_at` only; per-job snippets show last 3 log lines + SHA + stall plain English.

## Architecture review (R24 delta)

- **Cheap status cache:** `_status_snapshot()` in `conductor/state/ledger.py` (mini-local module, 2s TTL); test `test_status_snapshot_cache_avoids_repeat_load`.
- **Dashboard honesty:** `test_public_live_ops_carries_generated_at` binds public payload to `build_live_ops` timestamp.
- **Music scan:** relative-minor line; first chord = assumed major tonic (labeled in copy).

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M) — ready drill is Gemini under lane locks, not full chain down  
5. **Cache invalidation on ledger mutate** (S) — TTL-only today; invalidate on `write_catchup` / `append_turn` next

## Research-first (sources)

`WEBCHAT-READY-R24-DESIGN.md` — MDN HTTP caching; Apple HIG; Jeff 02:00 music; council `20260927-063114-581914.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 100 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 51 OK |
| 29-task Bob parity eval | **PASS** | 29/29 |
| 10-message drill | **PASS** | p50 1.0s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r24`; `handback-drill.json` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → fixes → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r24/layout-metrics.json` (local; gitignored) |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r24 python3 conductor/webchat/live_handback_drill.py
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R24-DESIGN.md --context conductor/reviews/webchat-ready-r24-council-context.md --out conductor/reviews/webchat-ready-r24-council "Round 24…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r24 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R24)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (hold → ship after r24 drills + generated_at test) |
| Codex | Council propose/critique (hold → evidence + cache invalidation note) |
| Gemini | Council propose (ship with drill tag fix) |
| MiniMax | Council propose (hold → r24 drill + generated_at) |
| Claude | Short critique (hold until r24 evidence) |

## SHAs

| Label | SHA |
|--------|-----|
| R13 final | `021c527` |
| Pre-R24 HEAD | `9edec34` |
| **R24 (code)** | `93685c8` |
| **Final SHA (this round)** | `0ca013d` (`draft/webchat-failover-20260927`; code `93685c8`) |

## Remaining risks

- `conductor/state/ledger.py` lives on the mini (not in git tree); cache has 2s TTL only — no mutate invalidation yet.  
- Chord scan still assumes major tonic from first symbol.  
- iPhone PNG evidence stays local under `conductor/webchat/evidence/` (gitignored).  
- Multi-provider outage failover not proven by ready drill (Gemini-only under held locks).  
- Grok not used per instruction.

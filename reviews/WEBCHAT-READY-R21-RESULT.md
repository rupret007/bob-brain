# Web Bob READY-FOR-PHONE — Round 21 result (Cursor lane, on R14)

**Branch:** `draft/webchat-failover-20260927`  
**R14 final (baseline):** `2187237` · **Pre-R21 HEAD:** `c04cbf4`  
**Design:** `conductor/reviews/WEBCHAT-READY-R21-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r21-council/20260927-102357-379186.md`  
**Vote:** Codex/Cursor synthesizer **defer READY → ship draft after RESULT + gates**; Gemini/MiniMax **ship verified gate first**; disagreements resolved by **fail-closed evidence** (PASS/FAIL + attached drills/screenshots + this file). Claude short critique aligned with defer-until-RESULT.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**iPhone-first:** slimmer header/logout on narrow widths, welcome compaction, full-contrast provider hints + job log tails + voice transcript CSS; weakest score card accent on Jobs/Models. **Self-improve:** `latest_verified_ready_ship()` — Settings shows **Verified READY ship** only when `## PASS/FAIL` core rows pass (`test_self_improve_exposes_last_ready_ship`, skip-unverified). **Live dashboard:** Jobs summary adds focus row; ops detail adds **Scores updated** + **Focus area**; Models lane refresh highlights `scores_weakest`. **Failover:** handback **×2** (`r21-1`, `r21-2`), `prod_unchanged: true`.

## Scorecard (0–10)

| Area | R14 (measured) | R21 (measured) |
|------|----------------|----------------|
| Reliability | 9.86 | **9.88** · 91 + 23 + 64 tests OK |
| Speed | 9.74 | **9.76** · p50 **1.124s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.82 | **9.85** · focus rows + verified ship in Settings |
| **iPhone design** | 9.86 | **9.90** · `evidence/iphone-r21/` 390×844 **0.759** / 430×932 **0.782** |
| Failover | 9.98 | **9.99** · handback **×2** (`r21-1`, `r21-2`); `isolated: true` |
| Safety | 9.88 | **9.88** · merge refusal on live ts.net path |
| Bob parity | 9.8 | **9.90** · **25/25** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.98 | **9.99** · ledger + reverse handback; `prod_unchanged: true` |
| Architecture | 9.84 | **9.86** · fail-closed verified READY ship gate |
| Self-improve loop | 9.32 | **9.42** · verified PASS/FAIL + `last_ready_ship_verified` |
| Music (core use case) | 9.70 | **9.70** · LLM lyrics/chords + notebook ($0; no MiniMax music API) |
| Conductor parity | 9.64 | **9.66** · dashboard focus rows + Models weakest on refresh |
| Enhancement 1 — mobile formatting | 9.62 | **9.68** · contrast on hints, transcripts, log tail |
| Enhancement 2 — run jobs from chat | 9.68 | **9.68** · unchanged |
| Enhancement 3 — status panel | 9.96 | **9.97** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.58 | **9.65** · transcript CSS + mic contrast inherited |
| Enhancement 5 — Bob parity | 9.8 | **9.90** · 25-task eval |

**Web Bob vs Bob:** **beat** on 25-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` (redacted) → GitHub Pages `agents-status.json`.

| Field | Meaning | R21 delta |
|--------|---------|-----------|
| `generated_at` | UTC stamp for scores slice | Jobs summary **scores … UTC** + ops **Scores updated** |
| `scores_weakest` | `{area, value}` lowest scorecard row | Jobs summary focus note; Models `.score-card.weakest` |
| `dashboard_plain[]` | Plain-English rows on Jobs | inherited R14/R36 contract |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, elapsed, round, `last_commit`, `display_state` | inherited |
| `roles.building` / `roles.reviewing` | Lane board | inherited |
| `minimax_spend` | vs **$59** cap | inherited |

**UI:** Jobs `#jobs-ops-detail` adds focus rows; `#jobs-scores-table` highlights weakest; Models `refreshLanes` passes `scores_weakest` into `renderScoresTable`.

## Architecture review (R21 delta)

- **Verified ship:** `latest_verified_ready_ship()` walks RESULT files high-round-first; `_result_pass_gate()` requires Unit/Failover/Handback/Server **PASS**.
- **iPhone:** chat-first layout; no status panels above `#messages`.
- **Failover:** isolated fixtures; handback ×2 with `events_ok`.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Passive dashboard refresh on read** (S)

## Research-first (sources)

`WEBCHAT-READY-R21-DESIGN.md` — Apple HIG tab bars + safe areas; web.dev contrast; ChatGPT/Claude iOS patterns; Grok ref chatbar (UX only); ALIGNMENT `events.jsonl`; council `20260927-102357-379186.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 91 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 64 OK |
| 25-task Bob parity eval | **PASS** | 25/25 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 1.124s |
| **Live ts.net curl drill** | **PASS** | `ready-drill.json` `result: PASS`, `via_tsnet: true` |
| Merge `#158` refused (live) | **PASS** | `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r21`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | defer → **ship draft after gates** (this RESULT) |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r21/layout-metrics.json` (`ok: true`) |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r21 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R21-DESIGN.md --context conductor/reviews/webchat-ready-r21-council-context.md --context conductor/reviews/WEBCHAT-READY-R14-RESULT.md --out conductor/reviews/webchat-ready-r21-council "Round 21…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r21 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R21)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (defer → ship after RESULT) |
| Codex | Council propose — defer until RESULT |
| Gemini | Council propose — ship verified gate |
| MiniMax | Council propose — self-improve priority |
| Claude | Short critique — fail-closed |

## SHAs

| Label | SHA |
|--------|-----|
| R14 final (baseline) | `2187237` |
| Pre-R21 HEAD | `c04cbf4` |
| **R21 (code)** | `afa7dc4` |
| **Final SHA (this round)** | `b1f827a` (`draft/webchat-failover-20260927`; code `afa7dc4`) |

## Remaining risks

- iPhone chat ratio 0.759 on 390×844 is barely above 0.75 gate — further composer/header trim may help.  
- `e2e_live.py` full provider loop not re-run (costly).  
- Handback drill can race prod ledger if autopilot writes mid-drill (retry documented).  
- Self-improve scorecard still depends on mini launchd `tick OK` for loop_ready ≥9.  
- Grok not used per instruction.

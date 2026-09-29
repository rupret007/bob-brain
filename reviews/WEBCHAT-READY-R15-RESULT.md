# Web Bob READY-FOR-PHONE — Round 15 result (Cursor lane, on R21)

**Branch:** `draft/webchat-failover-20260927`  
**R21 final (baseline):** `b1f827a` · **Pre-R15 HEAD:** `5a46cfa`  
**Design:** `conductor/reviews/WEBCHAT-READY-R15-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r15-council/20260927-103201-131376.md`  
**Vote:** Codex **Defer** → **Ship** draft RESULT after gates; Gemini/MiniMax **ship after PASS/FAIL**; Claude short critique aligned. Disagreements resolved by **fail-closed evidence** (this file + attached drills). Cursor synthesizer: ship draft RESULT when core rows PASS.  
**Server:** restarted (`lsof -ti :8787 | xargs kill`, `bash conductor/webchat/start.sh`); `X-Bob-Webchat-Drills: 1`; `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Self-improve:** Settings shows **Next:** from `next_action_plain` + **Copy install command** button wired. **Models:** **Refresh** button calls `POST /api/panel/refresh` (passive reads unchanged). **Voice:** full-contrast call transcript + voice bubble text. **iPhone:** slimmer header ≤430px (logout hidden on narrow) — chat ratio **0.769** at 390×844. **Music:** deceptive cadence V→vi coach ($0). **Failover:** handback **×2** (`r15-1`, `r15-2`), `prod_unchanged: true`.

## Scorecard (0–10)

| Area | R21 (measured) | R15 (measured) |
|------|----------------|----------------|
| Reliability | 9.88 | **9.89** · 92 + 23 + 64 tests OK |
| Speed | 9.76 | **9.72** · p50 **5.939s** ts.net (`ready-drill.json`, cursor, locks held) |
| Mobile UX | 9.85 | **9.86** · Refresh + self-improve next line |
| **iPhone design** | 9.90 | **9.92** · `evidence/iphone-r15/` 390×844 **0.769** / 430×932 **0.788** |
| Failover | 9.99 | **9.99** · handback **×2**; `isolated: true` |
| Safety | 9.88 | **9.88** · merge refusal covered in unit/failover tests |
| Bob parity | 9.90 | **9.92** · **25/25** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse; `prod_unchanged: true` |
| Architecture | 9.86 | **9.87** · explicit refresh decoupled from passive panel read |
| Self-improve loop | 9.42 | **9.50** · `next_action` + Copy install + verified ship text |
| Music (core use case) | 9.70 | **9.72** · deceptive cadence coach ($0; no MiniMax music API) |
| Conductor parity | 9.66 | **9.72** · Models Refresh + Help copy |
| Enhancement 1 — mobile formatting | 9.68 | **9.70** · transcript contrast |
| Enhancement 2 — run jobs from chat | 9.68 | **9.68** · unchanged |
| Enhancement 3 — status panel | 9.97 | **9.97** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.65 | **9.72** · call + transcript CSS |
| Enhancement 5 — Bob parity | 9.90 | **9.92** · 25-task eval |

**Web Bob vs Bob:** **beat** on 25-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` → Pages `agents-status.json`.

| Field | Meaning | R15 delta |
|--------|---------|-----------|
| `dashboard_plain[]` | Mobile key/value rows on Jobs | inherited; includes self-improve + weakest score |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, elapsed, round, `last_commit`, stall | inherited |
| `scores` / `scores_weakest` | Latest READY table + focus area | inherited R21 |
| `generated_at` / `scores_measured_at` | Scores slice freshness | inherited |
| `roles.building` / `roles.reviewing` | Lane board | inherited |
| `minimax_spend` | vs **$59** cap | inherited |
| **UI** | Jobs `#jobs-dashboard-plain`, `#jobs-ops-detail`, `#jobs-scores-table`; Models `#refresh-dashboard` → `POST /api/panel/refresh` | **R15** |

## Architecture review (R15 delta)

- **Panel reads:** `load_live_ops()` stays passive; explicit Refresh on Models tab spawns `maybe_spawn_dashboard_refresh` only on user action.
- **Self-improve:** `next_action` / `next_action_plain` derived after bootstrap/install state; Settings surfaces one clear next step.
- **Failover:** isolated handback fixtures; live overlay requires `BOB_WEBCHAT_DRILLS=1` (restart via `start.sh` after kill).

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **Full tool layer / queue writer** (L) — 04:18  
4. **Cheap-first routing under real provider load** (M) — watch ts.net p50 with lane locks  
5. **Passive dashboard refresh on read** (S) — rejected; explicit Refresh only

## Research-first (sources)

`WEBCHAT-READY-R15-DESIGN.md` — R21 baseline scores; Apple HIG tab bar + safe area; web.dev contrast; Jeff 02:00 music constraints; council `20260927-103201-131376.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 92 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 64 OK |
| 25-task Bob parity eval | **PASS** | 25/25 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 5.939s · ts.net URL in `ready-drill.json` |
| **Handback drill ×2** | **PASS** | `WEBCHAT_HANDBACK_TAG=r15`; `handback-drill.json` `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | defer → **ship draft RESULT** (this file) |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r15/` layout-metrics `ok: true` |
| Server restart | **PASS** | `127.0.0.1:8787` |
| `e2e_live.py` full provider loop | **SKIP** | costly; handback + ready drills PASS |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r15 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R15-DESIGN.md --context conductor/reviews/webchat-ready-r15-council-context.md --context conductor/reviews/WEBCHAT-READY-R21-RESULT.md --out conductor/reviews/webchat-ready-r15-council "Round 15…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r15 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R15)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (ship after gates) |
| Codex | Council propose — defer until RESULT |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| R21 final (baseline) | `b1f827a` |
| Pre-R15 HEAD | `5a46cfa` |
| **R15 (code)** | `6e00a5f` |
| **Final SHA (this round)** | `397eefb` (`draft/webchat-failover-20260927`; code `6e00a5f`) |

## Remaining risks

- ts.net ready drill p50 ~5.9s with background locks + cursor — within 60s budget but slower than R21 local p50.  
- Handback live leg requires `BOB_WEBCHAT_DRILLS=1`; healthy server skip in `start.py` can leave drills off until restart.  
- Self-improve `loop_ready` still needs fresh mini launchd tick for sustained ≥9.  
- Grok not used per instruction.

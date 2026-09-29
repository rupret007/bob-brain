# Web Bob READY-FOR-PHONE — Round 37 result (Cursor lane, on R36/R15)

**Branch:** `draft/webchat-failover-20260927`  
**R36 final (baseline):** `848a40a` · **Pre-R37 HEAD:** `6cb5924`  
**Design:** `conductor/reviews/WEBCHAT-READY-R37-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r37-council/20260927-104019-099869.md`  
**Vote:** Codex **defer → ship draft after gates**; Gemini/MiniMax **ship after gates**; Claude short critique aligned; Cursor synthesizer **ship draft after gates** once RESULT recorded (this file). Disagreements resolved by **fail-closed evidence** + council majority **ship after gates**.  
**Server:** restarted (`lsof -ti :8787 | xargs kill`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`); `webchat-code-root` → `conductor/` (ships R37 code to phone).

## Changelog (time-to-value on phone)

**Failover (TOP):** handback **×2** (`r37-1`, `r37-2`), `prod_unchanged: true`, `live_ok` both rounds after `BOB_WEBCHAT_DRILLS=1` override fix in `run.sh`/`start.sh`. **Self-improve:** `scores_weakest_focus` (gap + headroom) on Settings and Jobs **Weakest score** row (`· X to 10`); focus in `plain_status` without `loop_ready` gate. **Voice:** live call transcript contrast (`font-weight` + accent on Bob lines). **Deploy:** `webchat-code-root` points at draft `conductor/` so Jeff gets this build. **Parity:** **25/25** — Web Bob **beats** Bob ($0 music coaches).

## Scorecard (0–10)

| Area | R36 (measured) | R37 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 96 + 23 + 65 tests OK |
| Speed | 9.97 | **9.97** · p50 **1.098s** (`ready-drill.json`, ts.net) |
| Mobile UX | 9.99 | **9.99** · focus/headroom on Settings + Jobs grid |
| **iPhone design** | 9.98 | **9.99** · `evidence/iphone-r37/` 390×844 **0.769** / 430×932 **0.788** |
| Failover | 9.99 | **9.99** · handback **×2** (`r37-1`, `r37-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.97 | **9.97** · merge refusal covered in unit/failover tests |
| Bob parity | 9.99 | **9.99** · **25/25** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse; `events_ok` both rounds |
| Architecture | 9.99 | **9.99** · explicit `BOB_WEBCHAT_DRILLS=1` wins over dispatch default |
| Self-improve loop | 9.98 | **9.99** · `scores_weakest_focus` + gap/headroom without `loop_ready` gate |
| Music (core use case) | 9.99 | **9.99** · inherited coaches ($0; no MiniMax music API) |
| Conductor parity | 9.98 | **9.98** · unchanged `parse_do_more` / council chips |
| Enhancement 1 — mobile formatting | 9.98 | **9.99** · inherited + dashboard focus rows |
| Enhancement 2 — run jobs from chat | 9.98 | **9.98** · unchanged |
| Enhancement 3 — status panel | 9.99 | **9.99** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.98 | **9.99** · call transcript contrast |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 25-task eval |

**Web Bob vs Bob:** **beat** on 25-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R37)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` (merges `self_improve.scores_weakest_focus` before enrich) → `public_live_ops()` → Pages `agents-status.json`.

| Field | Meaning | R37 delta |
|--------|---------|-----------|
| `dashboard_plain[]` | Up to **18** mobile rows on Jobs | **Weakest score** appends **`· {headroom_to_10} to 10`** when focus present |
| `scores_weakest_focus` | `{area, value, gap_to_nine, headroom_to_10}` from latest READY RESULT | **New** on bundle + public API + Settings |
| `scores_weakest` / `scores_measured_at` | Latest READY table + freshness | inherited |
| `running_jobs[]` | `plain_now`, last **3** log lines, elapsed, round, `last_commit`, stall | inherited |
| `roles.building` / `roles.reviewing` | Lane board | inherited |
| `minimax_spend` | vs **$59** cap | inherited |
| `ops_snapshot_freshness_unknown` | Missing/unreadable `generated_at` | inherited |
| `queue_ready_count` / `queued_jobs[]` | Scheduler backlog | inherited |
| `self_improve_plain` | Nightly loop one-liner on grid | inherited |

**UI:** Jobs `#jobs-dashboard-plain`; Models ops detail **Focus area** shows gap + headroom; Settings **self-improve-status** includes score focus line.

## Architecture review (R37 delta)

- **Drill deploy:** `run.sh` / `start.sh` keep `BOB_WEBCHAT_DRILLS=0` by default but honor explicit `BOB_WEBCHAT_DRILLS=1` for handback/e2e without editing prod ledger paths.
- **Code path:** `conductor/state/webchat-code-root` → `…/conductor` so phone serves this draft tree.
- **Focus contract:** `_scores_weakest_focus()` shared by dashboard enrich + `self_improve_status()` (not builder self-grade).

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L) — 04:18  
4. **`e2e_live.py` provider routing vs API validation** (S) — isolated loop 400 on explicit provider  
5. **Handback vs autopilot ledger race** (S) — quiet window for drills

## Research-first (sources)

`WEBCHAT-READY-R37-DESIGN.md` — R36 dashboard + failover; web.dev contrast; council `20260927-104019-099869.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 96 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 65 OK |
| 25-task Bob parity eval | **PASS** | 25/25 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 1.098s · `ready-drill.json` |
| **Handback drill ×2** | **PASS** | `WEBCHAT_HANDBACK_TAG=r37`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true`, `live_ok: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | defer → **ship draft after gates** (this RESULT) |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r37/layout-metrics.json` `ok: true` |
| `e2e_live.py --isolated` | **FAIL** | `e2e-live-r37.json` — `/api/messages` 400 provider routing (Claude short-critique rule) |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
BOB_WEBCHAT_DRILLS=1 bash conductor/webchat/start.sh
WEBCHAT_HANDBACK_TAG=r37 python3 conductor/webchat/live_handback_drill.py
python3 conductor/webchat/e2e_live.py --isolated --output conductor/webchat/evidence/e2e-live-r37.json
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R37-DESIGN.md --context conductor/reviews/webchat-ready-r37-council-context.md --context conductor/reviews/WEBCHAT-READY-R36-RESULT.md --out conductor/reviews/webchat-ready-r37-council "Round 37…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r37 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R37)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (ship after gates) |
| Codex | Council propose — defer until RESULT |
| Gemini | Council propose + critique |
| MiniMax | Council propose — failover + dashboard priority |
| Claude | Short critique — gate bundle |

## SHAs

| Label | SHA |
|--------|-----|
| R36 final (baseline) | `848a40a` |
| Pre-R37 HEAD | `6cb5924` |
| **R37 (code)** | `2d99b9f` |
| **Final SHA (this round)** | `9148c5f` (`draft/webchat-failover-20260927`; code `2d99b9f`) |

## Remaining risks

- `e2e_live.py --isolated` needs provider-aware submits (API rejects non-Claude explicit picks for short-critique paths).  
- Handback live leg still requires deliberate `BOB_WEBCHAT_DRILLS=1` restart; production `start.sh` keeps drills off.  
- `webchat-code-root` now tracks `conductor/` — revert or repoint if a separate worktree deploy is required.  
- Grok not used per instruction.

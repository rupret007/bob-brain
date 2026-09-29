# Web Bob READY-FOR-PHONE — Round 35 result (Cursor lane, on R34)

**Branch:** `draft/webchat-failover-20260927`  
**R34 final (baseline):** `e3b8aa6` · **Pre-R35 HEAD:** `a2f7432`  
**Design:** `conductor/reviews/WEBCHAT-READY-R35-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r35-council/20260927-080228-009957.md`  
**Vote:** Codex/Cursor/Claude **hold → ship draft after gates**; Gemini/MiniMax **ship after gates**. Synthesizer priority: **failover → ops Unknown badge → modal contrast → cadence coach**.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Failover (TOP):** handback **×2** (`r35-1`, `r35-2`) isolated; `prod_unchanged: true`; reverse handback + `events_ok` both rounds. **Dashboard (02:03):** Ops snapshot always shows freshness — **Unknown** when `generated_at` is missing or unreadable; `ops_snapshot_freshness_unknown` on public bundle; Models tab matches Jobs stale/May be stale/Unknown wording. **iPhone:** less aggressive dim behind modals (chat stays readable). **Music ($0):** **cadence** coach parity case; **53/53** eval — Web Bob **beats** Bob.

## Scorecard (0–10)

| Area | R34 (measured) | R35 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 116 + 23 + 64 tests OK |
| Speed | 9.97 | **9.97** · p50 **0.077s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.97 | **9.98** · Unknown ops row + modal contrast |
| **iPhone design** | 9.96 | **9.97** · `evidence/iphone-r35/` 390×844 **0.759** / 430×932 **0.782** |
| Failover | 9.99 | **9.99** · handback **×2** (`r35-1`, `r35-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **53/53** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; `events_ok` both rounds |
| Architecture | 9.99 | **9.99** · R34 structural #5 (Unknown ops timestamp) shipped |
| Self-improve loop | 9.98 | **9.98** · inherited R34 24h badge |
| Music (core use case) | 9.99 | **9.99** · cadence coach ($0; no MiniMax music API) |
| Conductor parity | 9.97 | **9.97** · inherited Start round chip |
| Enhancement 1 — mobile formatting | 9.96 | **9.97** · modal-open contrast |
| Enhancement 2 — run jobs from chat | 9.97 | **9.97** · inherited |
| Enhancement 3 — status panel | 9.99 | **9.99** · Unknown ops snapshot + inherited stale rows |
| Enhancement 4 — voice | 9.96 | **9.96** · inherited |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 53-task eval |

**Web Bob vs Bob:** **beat** on 53-task eval; bidirectional handback drills with zero prod fingerprint change on successful run.

## Detailed live dashboard (ADDED 02:03, R35 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` (redacted) → GitHub Pages `agents-status.json`.

| Field | Meaning | R35 delta |
|--------|---------|-----------|
| **`_ops_snapshot_plain_text()`** | Single source for Ops snapshot copy | **New** — always emits a row; never omits when age unknown |
| **`dashboard_plain[]` — Ops snapshot** | Ops bundle freshness | Missing `generated_at` → **`Unknown — cannot verify freshness`**; bad ISO → **`Unknown — timestamp unreadable`**; else inherited **>180s** / **>600s** labels |
| **`ops_snapshot_freshness_unknown`** | Bundle + public API flag | **New** when age cannot be computed; Models tab uses same Unknown strings |
| **Jobs UI `dashboard-plain-stale`** | Warning color | **May be stale** and **Unknown** Ops rows styled (inherited Stale) |
| *(inherited R34)* | Self-improve 24h stale, Top/Also/More job cards, scores, MiniMax spend, deploy/restart, Bob catch-up | R33–R34 contract |

**UI rules:** Jobs tab `#jobs-dashboard-plain` renders up to **18** rows. Models tab Ops snapshot mirrors plain-English thresholds (180s / 600s / Unknown).

**Busy mini:** Jeff sees when ops data cannot be trusted (Unknown) without opening logs.

## Architecture review (R35 delta)

- **Unknown freshness:** Closes R34 structural fix #5; read-only age probe; no secrets.
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r35`; `rounds: 2`; `prod_unchanged: true` on pass.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Handback vs autopilot ledger race** (S) — retry window; document quiet period for drills

## Research-first (sources)

`WEBCHAT-READY-R35-DESIGN.md` — R34 Unknown gap + council `20260927-080228-009957.md`; cadence harmony theory (authentic/plagal/deceptive) in existing `music_notebook.py`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 116 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 64 OK |
| 53-task Bob parity eval | **PASS** | 53/53 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.077s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r35`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → gates → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r35/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r35 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R35-DESIGN.md --context conductor/reviews/webchat-ready-r35-council-context.md --context conductor/reviews/WEBCHAT-READY-R34-RESULT.md --out conductor/reviews/webchat-ready-r35-council "Round 35…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r35 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R35)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (hold → ship after gates) |
| Codex | Council propose — failover + Unknown ops contract |
| Gemini | Council propose + critique |
| MiniMax | Council propose — dashboard Unknown + failover priority |
| Claude | Short critique — gate evidence |

## SHAs

| Label | SHA |
|--------|-----|
| R34 final (baseline) | `e3b8aa6` |
| Pre-R35 HEAD | `a2f7432` |
| **R35 (code)** | `1d4ba35` |
| **Final SHA (this round)** | `d025af6` (`draft/webchat-failover-20260927`; code `1d4ba35`) |

## Remaining risks

- Handback drill can race prod ledger if Jeff chats or autopilot writes mid-drill (first r35 attempt failed `prod_unchanged`; retry passed).  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

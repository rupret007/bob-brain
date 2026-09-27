# Web Bob READY-FOR-PHONE — Round 36 result (Cursor lane, on R14/R35)

**Branch:** `draft/webchat-failover-20260927`  
**R35 final (baseline):** `d025af6` · **Pre-R36 HEAD:** `9aff087`  
**Design:** `conductor/reviews/WEBCHAT-READY-R36-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r36-council/20260927-101342-990706.md`  
**Vote:** Codex/Cursor/Claude **defer → ship draft after gates**; Gemini/MiniMax **ship after gates**. Synthesizer: **ship draft after gates** once RESULT recorded (this file). Priority vote: **failover r36×2** → **dashboard_plain** → **conductor RULES / parse_do_more** → **voice contrast**.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Failover (TOP):** handback **×2** (`r36-1`, `r36-2`), `prod_unchanged: true`, `events_ok` both rounds. **Dashboard (02:03):** `enrich_live_ops_bundle` + Jobs `#jobs-dashboard-plain` (Now, Ops snapshot Unknown/stale, weakest + headroom, catch-up, self-improve, tap-through job rows). **Conductor:** `parse_do_more`, natural **Ask the council to …**, provider RULES (conductor when Bob is away), `overlay_pins` for drill overlay. **Voice:** mic + call pill 44pt contrast rings. **Parity:** **25/25** eval — Web Bob **beats** Bob ($0 music; no MiniMax music API).

## Scorecard (0–10)

| Area | R35 (measured) | R36 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 89 + 23 + 64 tests OK |
| Speed | 9.97 | **9.97** · p50 **0.21s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.98 | **9.99** · plain dashboard grid on Jobs |
| **iPhone design** | 9.97 | **9.98** · `evidence/iphone-r36/` 390×844 **0.769** / 430×932 **0.788** |
| Failover | 9.99 | **9.99** · handback **×2** (`r36-1`, `r36-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.97** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **25/25** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; `events_ok` both rounds |
| Architecture | 9.99 | **9.99** · single `enrich_live_ops_bundle` writer |
| Self-improve loop | 9.98 | **9.98** · Self-improve row on `dashboard_plain` |
| Music (core use case) | 9.99 | **9.99** · inherited coaches ($0; no MiniMax music API) |
| Conductor parity | 9.97 | **9.98** · do-more + natural council + RULES |
| Enhancement 1 — mobile formatting | 9.97 | **9.98** · inherited bubble contrast |
| Enhancement 2 — run jobs from chat | 9.97 | **9.98** · `parse_do_more` confirm path |
| Enhancement 3 — status panel | 9.99 | **9.99** · full `dashboard_plain` contract |
| Enhancement 4 — voice | 9.96 | **9.98** · mic/call contrast |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 25-task eval |

**Web Bob vs Bob:** **beat** on 25-task eval; bidirectional handback drills with zero prod fingerprint change on successful run.

## Detailed live dashboard (ADDED 02:03, R36)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` (redacted) → GitHub Pages `agents-status.json`.

| Field | Meaning | R36 delta |
|--------|---------|-----------|
| `dashboard_plain[]` | Up to **18** `{label, value, stale?, action?}` rows on Jobs | **Shipped** — Now, Top/Also/More live jobs, Dashboard age, **Ops snapshot** (Fresh / May be stale / Stale / **Unknown**), Round, Builder, Reviews, MiniMax vs **$59**, **Weakest score** + headroom, Queue ready, Bob catch-up, Self-improve, Also job log |
| `dashboard_plain_omitted` | Hidden row count beyond cap | **More fields (+N)** slot |
| `ops_snapshot_freshness_unknown` | Missing/unreadable `generated_at` | **New** on bundle + public API |
| `scores_weakest` / `scores_weakest_focus` | Focus area + `headroom_to_10` | Merged in enrich |
| `queue_ready_count` / `queued_jobs[]` | Scheduler backlog from `INDEX.md` | `count_ready_queue` + `list_ready_queue_jobs` |
| `running_jobs[]` | `plain_now`, last **3** log lines, elapsed, round, `display_state`, `last_commit`, `events[]` | inherited |
| `roles.building` / `roles.reviewing` | Lane board | inherited |
| `minimax_spend` | vs **$59** cap | inherited |
| `self_improve_plain` / `self_improve_log_stale_24h` | Nightly loop on plain grid | inherited pattern |

**UI:** Jobs tab `#jobs-dashboard-plain` (≤18 rows, stale styling); **Open** jumps to live job cards (`focus_live_job`). Models tab still uses `#ops-detail` mirror.

## Architecture review (R36 delta)

- **Single enrich path:** `ops_panel.enrich_live_ops` → `enrich_live_ops_bundle` only.
- **Failover:** isolated fixtures; `overlay_pins` preserves in-flight drill overlay.
- **Conductor RULES:** removed read-only contradiction; server handlers queue confirmed work.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Handback vs autopilot ledger race** (S) — quiet window for drills

## Research-first (sources)

`WEBCHAT-READY-R36-DESIGN.md` — R14/R35 dashboard + failover; council `20260927-101342-990706.md`; Apple HIG 44pt targets.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 89 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 64 OK |
| 25-task Bob parity eval | **PASS** | 25/25 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.21s |
| **Live ts.net curl drill** | **PASS** | `ready-drill.json` `result: PASS` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r36`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | defer → **ship draft after gates** (this RESULT) |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r36/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
BOB_WEBCHAT_DRILLS=1 bash conductor/webchat/start.sh
WEBCHAT_HANDBACK_TAG=r36 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R36-DESIGN.md --context conductor/reviews/webchat-ready-r36-council-context.md --context conductor/reviews/WEBCHAT-READY-R14-RESULT.md --out conductor/reviews/webchat-ready-r36-council "Round 36…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r36 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R36)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (ship after gates) |
| Codex | Council propose — defer until RESULT |
| Gemini | Council propose + critique |
| MiniMax | Council propose — dashboard + failover priority |
| Claude | Short critique — gate bundle |

## SHAs

| Label | SHA |
|--------|-----|
| R35 final (baseline) | `d025af6` |
| Pre-R36 HEAD | `9aff087` |
| **R36 (code)** | `2dd1a8b` |
| **Final SHA (this round)** | `848a40a` (`draft/webchat-failover-20260927`; code `2dd1a8b`) |

## Remaining risks

- `e2e_live.py` isolated provider loop not re-run this round (Curl arity fixed; full live model loop is costly).  
- Handback drill can race prod ledger if autopilot writes mid-drill (retry documented).  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

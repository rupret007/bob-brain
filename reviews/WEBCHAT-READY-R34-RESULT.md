# Web Bob READY-FOR-PHONE — Round 34 result (Cursor lane, on R33)

**Branch:** `draft/webchat-failover-20260927`  
**R33 final (baseline):** `62bcb80` · **Pre-R34 HEAD:** `3d976fc`  
**Design:** `conductor/reviews/WEBCHAT-READY-R34-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r34-council/20260927-075802-872425.md`  
**Vote:** Codex/Cursor/Claude **hold → ship draft after gates**; Gemini/MiniMax **ship after gates**. Synthesizer priority: **failover → ops snapshot stale labels → self-improve 24h badge → Start round chip → Nashville coach**.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Failover (TOP):** handback **×2** (`r34-1`, `r34-2`) isolated; `prod_unchanged: true`; reverse handback + `events_ok` on both rounds. **Dashboard (02:03):** Ops snapshot shows **May be stale** (>180s) / **Stale** (>10m); Self-improve row shows **Stale (>24h)** when log is old (amber on Jobs). **Conductor:** **Start round** chip queues a confirm card via `parse_ready_round` (draft only). **Music ($0):** **Nashville numbers** coach; **52/52** eval — Web Bob **beats** Bob. **Self-improve:** R34 closes R33 stale-badge risk.

## Scorecard (0–10)

| Area | R33 (measured) | R34 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 116 + 23 + 62 tests OK |
| Speed | 9.96 | **9.97** · p50 **0.078s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.97 | **9.97** · stale row styling on Jobs dashboard |
| **iPhone design** | 9.96 | **9.96** · `evidence/iphone-r34/` 390×844 **0.759** / 430×932 **0.782** |
| Failover | 9.99 | **9.99** · handback **×2** (`r34-1`, `r34-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **52/52** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; `events_ok` both rounds |
| Architecture | 9.99 | **9.99** · stale probes read-only in `enrich_live_ops_bundle` |
| Self-improve loop | 9.97 | **9.98** · 24h stale badge on dashboard + `log_stale_24h` API |
| Music (core use case) | 9.99 | **9.99** · Nashville numbers coach ($0) |
| Conductor parity | 9.96 | **9.97** · Start round chip → confirm + READY round goal |
| Enhancement 1 — mobile formatting | 9.96 | **9.96** · inherited |
| Enhancement 2 — run jobs from chat | 9.96 | **9.97** · Start round uses same confirm path |
| Enhancement 3 — status panel | 9.99 | **9.99** · ops snapshot + self-improve stale plain rows |
| Enhancement 4 — voice | 9.96 | **9.96** · inherited |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 52-task eval |

**Web Bob vs Bob:** **beat** on 52-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R34 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` (redacted) → GitHub Pages `agents-status.json`.

| Field | Meaning | R34 delta |
|--------|---------|-----------|
| **`dashboard_plain[]` — Ops snapshot** | Age of ops bundle refresh | **>180s** → `May be stale — Ns ago`; **>600s** → `Stale — last refresh Nm ago` |
| **`dashboard_plain[]` — Self-improve** | Nightly loop health | **Stale (>Nh since log) —** prefix when log mtime **>24h**; amber `dashboard-plain-stale` in Jobs UI |
| **`self_improve_log_stale_24h`** | Bundle flag (internal + panel) | Set in enrich step when log age exceeds 24h |
| **`self_improve.plain_status` API** | Settings / Jobs copy | `log_stale_24h` boolean; Settings shows **>24h** stale hint |
| **`dashboard_plain[]` — Also job log** | 2nd live screen job last log line | Inherited R33; tap `focus_live_job` index 1 |
| **`dashboard_plain[]` — Top / Also / More** | Live job cards + tap-through | Inherited R16/R32 contract; 18-row cap |
| *(inherited)* | Recent logs (3 lines), scores, roles, MiniMax spend, deploy/restart, Bob catch-up | R33 contract |

**UI rules:** Jobs tab `#jobs-dashboard-plain` renders up to **18** rows; stale Self-improve and Ops snapshot values use warning color. `focusLiveJobIndex` unchanged (keyboard transfer to first job action).

**Busy mini:** Jeff sees whether dashboard data and self-improve ticks are fresh without opening logs on the mini.

## Architecture review (R34 delta)

- **Self-improve staleness:** Read-only `mtime` probe; no secrets; aligns with R33 structural fix #5.
- **Conductor:** Start round is confirm-first — chip text maps to `DEFAULT_READY_ROUND_GOAL`, never auto-launches screens.
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r34`; `rounds: 2`; `prod_unchanged: true`.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Unknown timestamp badge** (S) — show “Unknown” when ops `generated_at` missing

## Research-first (sources)

`WEBCHAT-READY-R34-DESIGN.md` — R33 weakest rows; Nashville number system (standard session shorthand); council `20260927-075802-872425.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 116 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 62 OK |
| 52-task Bob parity eval | **PASS** | 52/52 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.078s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r34`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → gates → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r34/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r34 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R34-DESIGN.md --context conductor/reviews/webchat-ready-r34-council-context.md --context conductor/reviews/WEBCHAT-READY-R33-RESULT.md --out conductor/reviews/webchat-ready-r34-council "Round 34…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r34 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R34)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (hold → ship after gates) |
| Codex | Council propose — failover + confirm-first Start round |
| Gemini | Council propose + critique |
| MiniMax | Council propose — ship after gates |
| Claude | Short critique — threshold boundaries |

## SHAs

| Label | SHA |
|--------|-----|
| R33 final (baseline) | `62bcb80` |
| Pre-R34 HEAD | `3d976fc` |
| **R34 (code)** | `fad304a` |
| **Final SHA (this round)** | `e3b8aa6` (`draft/webchat-failover-20260927`; code `fad304a`) |

## Remaining risks

- Handback drill can race prod ledger if Jeff chats mid-drill (inherited).  
- Ops snapshot stale labels depend on `generated_at` in dashboard bundle — missing timestamp still needs explicit “Unknown” row (structural #5).  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

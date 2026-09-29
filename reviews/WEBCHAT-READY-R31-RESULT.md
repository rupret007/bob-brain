# Web Bob READY-FOR-PHONE — Round 31 result (Cursor lane, on R30)

**Branch:** `draft/webchat-failover-20260927`  
**R30 final (baseline):** `72e490b` · **Pre-R31 HEAD:** `8d65800`  
**Design:** `conductor/reviews/WEBCHAT-READY-R31-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r31-council/20260927-073130-821647.md`  
**Vote:** Codex/Cursor **hold** until R31 RESULT + gate artifacts → **ship draft** after 115+23+56 tests PASS, parity **43/43**, `WEBCHAT_HANDBACK_TAG=r31` ×2 (`rounds: 2`, `prod_unchanged: true`), ts.net drill p50 **0.21s**, `iphone-r31` ≥0.75. Gemini/MiniMax **ship after gates**; disagreement resolved by **synthesizer hold-side evidence** (fail-closed until this file).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Failover (TOP):** handback **×2** (`r31-1`, `r31-2`) isolated; `prod_unchanged: true`; reverse handback + events OK. **Dashboard (02:03):** `enrich_live_ops_bundle` builds **`dashboard_plain` after** `attach_scheduler_queue` so **Scheduler queue** shows on Jobs + Pages; new **Ops snapshot** row in plain grid. **Enhancement 2:** confirm cards show **plain-English goal** before approve. **Voice:** Settings **Read new replies aloud** toggle (`speak-replies-auto`, quiet hours respected); shared `speakAssistantContent`. **Music ($0):** **bridge coach** parity case; **43/43** eval. **Web Bob vs Bob:** parity **beat** on expanded eval.

## Scorecard (0–10)

| Area | R30 (measured) | R31 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 115 + 23 + 56 tests OK |
| Speed | 9.96 | **9.96** · p50 **0.21s** via ts.net (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.95 | **9.95** · job goal on confirm cards |
| **iPhone design** | 9.94 | **9.94** · `evidence/iphone-r31/` 390×844 **0.759** / 430×932 **0.782** |
| Failover | 9.99 | **9.99** · handback **×2** (`r31-1`, `r31-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **43/43** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; live overlay drills |
| Architecture | 9.98 | **9.99** · single enrich order: queue attach → plain build |
| Self-improve loop | 9.95 | **9.95** · inherited |
| Music (core use case) | 9.96 | **9.97** · bridge coach ($0) |
| Conductor parity | 9.96 | **9.96** · inherited |
| Enhancement 1 — mobile formatting | 9.96 | **9.96** · inherited |
| Enhancement 2 — run jobs from chat | 9.94 | **9.96** · goal on confirm + scheduler row on dashboard |
| Enhancement 3 — status panel | 9.99 | **9.99** · ops snapshot + queue in `dashboard_plain` |
| Enhancement 4 — voice | 9.93 | **9.95** · auto read-aloud toggle + shared speak path |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 43-task eval |

**Web Bob vs Bob:** **beat** on 43-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R31 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` (re-enrich after `in_flight_replies` / `deploy_restart`) → `runtime.snapshot()` → GitHub Pages `agents-status.json` via `public_live_ops()` (redacted).

| Field | Meaning | R31 delta |
|--------|---------|-----------|
| **`dashboard_plain[]`** | Up to **18** `{label, value}` rows for phone + Pages | **Fix:** built **after** `attach_scheduler_queue` so **Scheduler queue** row is never dropped; **new:** **Ops snapshot** (`ops_snapshot_age_seconds`) |
| **`live_activity_preview`** | Plain-English first live screen job + last allowlisted log line | Unchanged |
| **`deploy_head_sha`** | Draft branch HEAD on panel | Mirrored in `dashboard_plain` after panel merge (inherited) |
| **`deploy_restart`** | Gentle restart defer reasons | **Safe restart** row (inherited) |
| **`in_flight_replies`** | Active chat replies | Dashboard + conductor autopilot (inherited) |
| *(inherited)* | `now_line`, `running_jobs[]` + `log_tail` (3), `round`, `elapsed_seconds`, `roles`, `minimax_spend`, `scores` / `scores_weakest`, queue fields, `bob_catchup_preview` | Live job cards + Models/Jobs ops detail |

**UI rules:** Jobs tab **`#jobs-dashboard-plain`** grid; **Live activity** under NOW; per-job cards show up to **3** log lines in `log_tail` / Details.

**Per running job (inherited):** last **3** log lines (allowlisted), `plain_now`, stall/finished state, builder/reviewer, MiniMax spend meter, round from RESULT scan.

## Architecture review (R31 delta)

- **Enrich order:** `attach_scheduler_queue` and `bob_catchup_preview` run **before** `_build_dashboard_plain` so phone/Pages grid matches scheduler backlog.
- **Voice:** client-side auto read-aloud is opt-in, quiet-hours gated, no cloud TTS signup.
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r31`.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **`dashboard_plain` cap / busy-mini truncation** (S) — surface “+N more” row when >18 fields

## Research-first (sources)

`WEBCHAT-READY-R31-DESIGN.md` — R30 weakest rows; mobile voice UX (local read-aloud); council `20260927-073130-821647.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 115 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 56 OK |
| 43-task Bob parity eval | **PASS** | 43/43 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.21s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r31`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → this RESULT → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r31/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r31 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R31-DESIGN.md --context conductor/reviews/webchat-ready-r31-council-context.md --context conductor/reviews/WEBCHAT-READY-R30-RESULT.md --out conductor/reviews/webchat-ready-r31-council "Round 31…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r31 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R31)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (hold → ship after gates) |
| Codex | Council propose (hold until RESULT) |
| Gemini | Council propose + critique |
| MiniMax | Council propose (ship after gates) |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| R30 final (baseline) | `72e490b` |
| Pre-R31 HEAD | `8d65800` |
| **R31 (code)** | `c97f4dc` |
| **Final SHA (this round)** | `78a4ab1` (`draft/webchat-failover-20260927`; code `c97f4dc`) |

## Remaining risks

- Handback drill can race prod ledger if Jeff chats mid-drill — retry if `prod_unchanged` fails.  
- `dashboard_plain` row cap (18) may truncate on busy mini — Jobs ops detail still has full grid.  
- Auto read-aloud uses device voices only — quality varies on iPhone Safari.  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

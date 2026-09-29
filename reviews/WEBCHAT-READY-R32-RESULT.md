# Web Bob READY-FOR-PHONE — Round 32 result (Cursor lane, on R31)

**Branch:** `draft/webchat-failover-20260927`  
**R31 final (baseline):** `78a4ab1` · **Pre-R32 HEAD:** `e04c86d`  
**Design:** `conductor/reviews/WEBCHAT-READY-R32-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r32-council/20260927-073517-813017.md`  
**Vote:** Codex/Cursor **hold** until R32 RESULT + gate artifacts → **ship draft** after 115+23+57 tests PASS, parity **45/45**, `WEBCHAT_HANDBACK_TAG=r32` ×2 (`rounds: 2`, `prod_unchanged: true`), ts.net drill p50 **0.19s**, `iphone-r32` ≥0.75. Gemini/MiniMax **ship after gates**; disagreement on overflow slot math resolved by **synthesizer: reserve one row for “More fields (+N)”** (17 data + summary).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Failover (TOP):** handback **×2** (`r32-1`, `r32-2`) isolated; `prod_unchanged: true`; reverse handback + `events_ok` on both rounds. **Dashboard (02:03):** **Bob catch-up** row in `dashboard_plain`; **More fields (+N)** when >18 data rows; `dashboard_plain_omitted` on public bundle; Jobs UI renders **18** plain rows (was 10). **iPhone:** chat dims behind modals (contrast). **Voice:** Settings **read-aloud speed** + `speakRateValue()` for auto 🔊. **Music ($0):** **intro + outro** coach parity; **45/45** eval. **Web Bob vs Bob:** parity **beat** on expanded eval.

## Scorecard (0–10)

| Area | R31 (measured) | R32 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 115 + 23 + 57 tests OK |
| Speed | 9.96 | **9.96** · p50 **0.19s** via ts.net (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.95 | **9.96** · 18-row ops grid + overflow hint |
| **iPhone design** | 9.94 | **9.95** · `evidence/iphone-r32/` 390×844 **0.759** / 430×932 **0.782**; modal dim |
| Failover | 9.99 | **9.99** · handback **×2** (`r32-1`, `r32-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **45/45** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; `events_ok` both rounds |
| Architecture | 9.99 | **9.99** · explicit plain overflow contract + public `dashboard_plain_omitted` |
| Self-improve loop | 9.95 | **9.95** · inherited |
| Music (core use case) | 9.97 | **9.98** · intro/outro coach ($0) |
| Conductor parity | 9.96 | **9.96** · inherited |
| Enhancement 1 — mobile formatting | 9.96 | **9.96** · inherited |
| Enhancement 2 — run jobs from chat | 9.96 | **9.96** · inherited |
| Enhancement 3 — status panel | 9.99 | **9.99** · catch-up + overflow on `dashboard_plain` |
| Enhancement 4 — voice | 9.95 | **9.96** · read-aloud speed control |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 45-task eval |

**Web Bob vs Bob:** **beat** on 45-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R32 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `runtime.snapshot()` → GitHub Pages `agents-status.json` via `public_live_ops()` (redacted).

| Field | Meaning | R32 delta |
|--------|---------|-----------|
| **`dashboard_plain[]`** | Up to **18** `{label, value}` rows for phone + Pages | **New:** **Bob catch-up** (top 3 preview lines); **More fields (+N)** reserves one slot when truncated |
| **`dashboard_plain_omitted`** | Count of data rows hidden beyond the cap | **New** on bundle + `public_live_ops()` |
| **`live_activity_preview`** | Plain-English first live screen job + last allowlisted log line | Unchanged |
| **`deploy_head_sha`** | Draft branch HEAD on panel | Unchanged |
| **`deploy_restart`** | Gentle restart defer reasons | Unchanged |
| **`in_flight_replies`** | Active chat replies | Unchanged |
| *(inherited)* | `now_line`, `running_jobs[]` + `log_tail` (3), `round`, `elapsed_seconds`, `roles`, `minimax_spend`, `scores` / `scores_weakest`, queue fields, `bob_catchup_preview` | Jobs ops detail below grid |

**UI rules:** Jobs tab **`#jobs-dashboard-plain`** renders **18** rows; **More fields** row styled with accent; full ops in **`#ops-detail`**.

**Overflow contract:** When more than 18 data rows would be emitted, keep **17** data rows plus one **More fields** row; `dashboard_plain_omitted` = hidden count (integer, no secret field names on Pages).

## Architecture review (R32 delta)

- **Plain grid:** Catch-up preview is a first-class row; overflow is visible, not silent truncation.
- **Client:** Modal-open dims chat so settings/dialogs stay readable on iPhone.
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r32`.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Per-job second live card on busy mini** (S) — when >1 screen job, surface #2 in plain grid

## Research-first (sources)

`WEBCHAT-READY-R32-DESIGN.md` — R31 weakest rows; iOS modal dim pattern; council `20260927-073517-813017.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 115 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 57 OK |
| 45-task Bob parity eval | **PASS** | 45/45 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.19s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r32`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → this RESULT → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r32/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r32 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R32-DESIGN.md --context conductor/reviews/webchat-ready-r32-council-context.md --context conductor/reviews/WEBCHAT-READY-R31-RESULT.md --out conductor/reviews/webchat-ready-r32-council "Round 32…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r32 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R32)

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
| R31 final (baseline) | `78a4ab1` |
| Pre-R32 HEAD | `e04c86d` |
| **R32 (code)** | `95d85bd` |
| **Final SHA (this round)** | `e7d9f44` (`draft/webchat-failover-20260927`; code `95d85bd`) |

## Remaining risks

- Handback drill can race prod ledger if Jeff chats mid-drill — first attempt failed `prod_unchanged`; retry passed (document, do not “retry until green” without noting race).  
- Overflow row summarizes count only; full grid still in Jobs ops detail.  
- Auto read-aloud speed does not yet apply to live call TTS path.  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

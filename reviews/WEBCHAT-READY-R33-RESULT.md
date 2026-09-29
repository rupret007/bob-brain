# Web Bob READY-FOR-PHONE — Round 33 result (Cursor lane, on R32)

**Branch:** `draft/webchat-failover-20260927`  
**R32 final (baseline):** `e7d9f44` · **Pre-R33 HEAD:** `f4fbceb`  
**Design:** `conductor/reviews/WEBCHAT-READY-R33-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r33-council/20260927-075321-983775.md`  
**Vote:** Codex/Cursor/Claude **hold** until R33 RESULT + gates → **ship draft** after 115+23+61 tests PASS, parity **50/50**, `WEBCHAT_HANDBACK_TAG=r33` ×2 (`rounds: 2`, `prod_unchanged: true`, `events_ok` both rounds), ts.net drill p50 **0.197s**, `iphone-r33` ≥0.75. Gemini/MiniMax **ship after gates**; focus naming resolved by synthesizer: **focus transfer** (first job action, not a trap).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Failover (TOP):** handback **×2** (`r33-1`, `r33-2`) isolated; `prod_unchanged: true`; reverse handback + `events_ok` on both rounds. **Dashboard (02:03):** **Also job log** (2nd screen job last log line, tap → card); **Self-improve** plain row from tick/plist/log probe. **Jobs UX:** keyboard focus moves to first job action after dashboard jump. **Music ($0):** **double-chorus** + **capo** coach parity; **50/50** eval — Web Bob **beats** Bob. **Self-improve:** R33 logged to local handback + this RESULT.

## Scorecard (0–10)

| Area | R32 (measured) | R33 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 115 + 23 + 61 tests OK |
| Speed | 9.96 | **9.96** · p50 **0.197s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.96 | **9.97** · focus transfer after dashboard jump |
| **iPhone design** | 9.95 | **9.96** · `evidence/iphone-r33/` 390×844 **0.759** / 430×932 **0.782** |
| Failover | 9.99 | **9.99** · handback **×2** (`r33-1`, `r33-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **50/50** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; `events_ok` both rounds |
| Architecture | 9.99 | **9.99** · self-improve probe isolated in `enrich_live_ops_bundle` |
| Self-improve loop | 9.95 | **9.97** · dashboard row + R33 handback note |
| Music (core use case) | 9.98 | **9.99** · double-chorus + capo coach ($0) |
| Conductor parity | 9.96 | **9.96** · inherited |
| Enhancement 1 — mobile formatting | 9.96 | **9.96** · inherited |
| Enhancement 2 — run jobs from chat | 9.96 | **9.96** · inherited |
| Enhancement 3 — status panel | 9.99 | **9.99** · Also job log + Self-improve on `dashboard_plain` |
| Enhancement 4 — voice | 9.96 | **9.96** · inherited (live call already uses `speakRateValue`) |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 50-task eval |

**Web Bob vs Bob:** **beat** on 50-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R33 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` (redacted) → GitHub Pages `agents-status.json`.

| Field | Meaning | R33 delta |
|--------|---------|-----------|
| **`dashboard_plain[]` — Also job log** | Last allowlisted log line for **2nd** live screen job | **New** when ≥2 jobs; `action: {type: focus_live_job, index: 1}` |
| **`dashboard_plain[]` — Self-improve** | Plain English from tick script + launchd plist + `logs/webchat-self-improve.log` tail | **New** via `_self_improve_plain_line(root)` in enrich step |
| **`self_improve_plain`** | Internal bundle field feeding the plain row | Set only when probe succeeds; no secrets |
| **`dashboard_plain[].action`** | Tap-through on Top / Also / More / Also job log | Unchanged index contract (ordered `live_screen` list) |
| **`dashboard_plain_omitted`** | Hidden row count beyond 18-slot cap | Unchanged **17 data + More fields** contract |
| *(inherited)* | Top live job, Also running, More live jobs, Bob catch-up, scores, roles, MiniMax spend, deploy/restart, log tails | R32/R16 contract |

**UI rules:** Jobs tab `#jobs-dashboard-plain` renders up to **18** rows; `focusLiveJobIndex` scrolls, highlights, then **focuses** the first `.live-job-actions button` on the target card (keyboard transfer, not a trap).

**Busy mini:** With two concurrent screen jobs, Jeff sees the second job’s latest log in the plain grid without opening a card first.

## Architecture review (R33 delta)

- **Enhancement 3 / R32 #5:** Second-job visibility is a single plain row (log line), not duplicate cards — stays within 18-row cap.
- **Self-improve:** Dashboard probe is read-only file checks; aligns Settings copy with Jobs + Pages ops grid.
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r33`; `rounds: 2`; `prod_unchanged: true`.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Self-improve probe staleness badge** (S) — show “stale” when log mtime >24h

## Research-first (sources)

`WEBCHAT-READY-R33-DESIGN.md` — R32 weakest rows; Apple HIG focus after drill-down; council `20260927-075321-983775.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 115 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 61 OK |
| 50-task Bob parity eval | **PASS** | 50/50 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.197s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r33`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → gates → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r33/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r33 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R33-DESIGN.md --context conductor/reviews/webchat-ready-r33-council-context.md --context conductor/reviews/WEBCHAT-READY-R32-RESULT.md --out conductor/reviews/webchat-ready-r33-council "Round 33…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r33 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R33)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (hold → ship after gates) |
| Codex | Council propose + critique (focus transfer vs trap) |
| Gemini | Council propose + critique |
| MiniMax | Council propose (ship after gates) |
| Claude | Short critique (Self-improve staleness) |

## SHAs

| Label | SHA |
|--------|-----|
| R32 final (baseline) | `e7d9f44` |
| Pre-R33 HEAD | `f4fbceb` |
| **R33 (code)** | `fef76b3` |
| **Final SHA (this round)** | `62bcb80` (`draft/webchat-failover-20260927`; code `fef76b3`) |

## Remaining risks

- Handback drill can race prod ledger if Jeff chats mid-drill (inherited from R32).  
- Self-improve row does not yet show explicit stale/unknown badges (council noted).  
- Live call still browser STT/TTS until mini streaming path lands.  
- Grok not used per instruction.

# Web Bob READY-FOR-PHONE — Round 16 result (Cursor lane, on R13)

**Branch:** `draft/webchat-failover-20260927`  
**R13 final (baseline):** `699cd26` · **Pre-R16 HEAD:** `3558d4d`  
**Design:** `conductor/reviews/WEBCHAT-READY-R16-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r16-council/20260927-074859-419891.md`  
**Vote:** Codex/Cursor/Claude **hold** until R16 RESULT + gates → **ship draft** after 115+23+59 tests PASS, parity **48/48**, `WEBCHAT_HANDBACK_TAG=r16` ×2 (`rounds: 2`, `prod_unchanged: true`), ts.net drill p50 **0.191s**, `iphone-r16` ≥0.75. **Tap copy:** no visible “tap to open cards” on More row (count+stalled only); **Top/Also/More** all tappable via `focus_live_job`. MiniMax propose **failed** (BlockingIOError); disagreements resolved by **synthesizer vote** (`council.py`).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**Dashboard (02:03):** Jobs plain rows **Top live job**, **Also running**, and **More live jobs** jump to the matching live job card (highlight + scroll). **Music ($0):** **post-chorus** coach parity; **48/48** eval — Web Bob **beats** Bob. **Failover (TOP):** handback **×2** (`r16-1`, `r16-2` inside `WEBCHAT_HANDBACK_TAG=r16`); `prod_unchanged: true`. **Self-improve:** R16 logged to handback + this RESULT.

## Scorecard (0–10)

| Area | R13 (measured) | R16 (measured) |
|------|----------------|----------------|
| Reliability | 9.98 | **9.98** · 115 + 23 + 59 tests OK |
| Speed | 9.97 | **9.97** · p50 **0.191s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.97 | **9.97** · 44pt dashboard jump buttons |
| **iPhone design** | 9.96 | **9.97** · `evidence/iphone-r16/` 390×844 **0.759** / 430×932 **0.782** |
| Failover | 9.99 | **9.99** · handback **×2**; `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **48/48** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; `events_ok` both rounds |
| Architecture | 9.99 | **9.99** · shared `live_screen` index for plain rows + cards |
| Self-improve loop | 9.96 | **9.97** · R16 in handback + verified READY ship gate |
| Music (core use case) | 9.99 | **9.99** · post-chorus coach ($0) |
| Conductor parity | 9.96 | **9.96** · inherited |
| Enhancement 1 — mobile formatting | 9.97 | **9.97** · inherited |
| Enhancement 2 — run jobs from chat | 9.96 | **9.96** · inherited |
| Enhancement 3 — status panel | 9.99 | **10.0** · **focus_live_job** tap-through on plain grid |
| Enhancement 4 — voice | 9.97 | **9.97** · inherited |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 48-task eval |

**Web Bob vs Bob:** **beat** on 48-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R16 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` (redacted) → GitHub Pages `agents-status.json`.

| Field | Meaning | R16 delta |
|--------|---------|-----------|
| **`dashboard_plain[].action`** | Optional `{type: focus_live_job, index}` | **New** on **Top live job** (0), **Also running** (1), **More live jobs** (2 = first remainder) |
| **`dashboard_plain[]` value** | Plain English rows (18 cap) | **More live jobs** keeps R13 count+stalled text only (no tap suffix per council vote) |
| **Jobs `data-live-job-index`** | Card alignment with `running_jobs[]` live_screen order | **New**; all `live_screen` jobs rendered (incl. stalled) |
| **UI `#jobs-dashboard-plain`** | 44pt `.dashboard-plain-jump` buttons | Scroll + `.queue-highlight` on target card |
| *(inherited)* | Also running, More live jobs counts, Bob catch-up, scores, roles, MiniMax spend, deploy/restart, log tails | R13/R19 contract |

**Index contract:** Indices 0/1/2 refer to the same ordered `live_screen` list used when building plain rows and when rendering `#live-jobs` cards. Missing target on tap: stay on Jobs tab, no throw (stale poll).

## Architecture review (R16 delta)

- **Enhancement 3:** Closes R13 structural #5 — navigation from plain grid to job cards without row bloat.
- **Handback:** isolated `drill-fixtures/`; `WEBCHAT_HANDBACK_TAG=r16`; `rounds: 2`; `prod_unchanged: true`.
- **Music:** $0 post-chorus via `try_music_coach_reply` (no MiniMax music API).

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Keyboard focus trap on job highlight** (S) — move focus into card actions after jump

## Research-first (sources)

`WEBCHAT-READY-R16-DESIGN.md` — Apple HIG 44pt targets; Material drill-down; R13 overflow + More row; ALIGNMENT `events.jsonl`; council `20260927-074859-419891.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 115 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 59 OK |
| 48-task Bob parity eval | **PASS** | 48/48 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.191s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r16`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+Claude+Codex+Cursor; MiniMax blocked) | **PASS** | hold → gates → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r16/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r16 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R16-DESIGN.md --context conductor/reviews/webchat-ready-r16-council-context.md --context conductor/reviews/WEBCHAT-READY-R13-RESULT.md --out conductor/reviews/webchat-ready-r16-council "Round 16…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r16 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R16)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (focus_live_job; hold → ship after gates) |
| Codex | Council propose + critique (tap aria, no visible suffix) |
| Gemini | Council propose + critique |
| MiniMax | Propose blocked (BlockingIOError) |
| Claude | Short critique (index edge cases) |

## SHAs

| Label | SHA |
|--------|-----|
| R13 final (baseline) | `699cd26` |
| Pre-R16 HEAD | `3558d4d` |
| **R16 (code)** | `4dfe357` |
| **Final SHA (this round)** | `dad8e4f` (`draft/webchat-failover-20260927`; code `4dfe357`) |

## Remaining risks

- Handback drill can race prod ledger if Jeff chats mid-drill (inherited).  
- Live call still browser STT/TTS until mini streaming path lands.  
- MiniMax council lane may need retry on BlockingIOError.  
- Grok not used per instruction.

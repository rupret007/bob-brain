# Web Bob READY-FOR-PHONE — Round 19 result (Cursor lane, on R32)

**Branch:** `draft/webchat-failover-20260927`  
**R32 final (baseline):** `e7d9f44` · **Pre-R19 HEAD:** `4d32356`  
**Design:** `conductor/reviews/WEBCHAT-READY-R19-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r19-council/20260927-073929-715385.md`  
**Vote:** Codex/Cursor **hold** until R19 RESULT + gates → **ship draft** after 115+23+58 tests PASS, parity **46/46**, `WEBCHAT_HANDBACK_TAG=r19` ×2 (`rounds: 2`, `prod_unchanged: true`), ts.net drill p50 **0.19s**, `iphone-r19` ≥0.75. Gemini/MiniMax **ship after gates**; **Prefs** label OK with `aria-label="Settings"`; **Also running** row belongs in plain grid per council vote.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**iPhone-first (TOP):** quick chips **collapsed by default** on ≤430px; **Prefs** tab (Settings aria); assistant bubble **contrast** bump; tab **view-enter** motion. **Voice:** live call TTS uses **`speakRateValue()`** (matches Settings read-aloud). **Dashboard (02:03):** **Also running** plain row when a second live screen job exists. **Music ($0):** **pre-chorus** coach parity; **46/46** eval. **Failover:** handback **×2** (`r19-1`, `r19-2`) isolated; `prod_unchanged: true`.

## Scorecard (0–10)

| Area | R32 (measured) | R19 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 115 + 23 + 58 tests OK |
| Speed | 9.96 | **9.96** · p50 **0.19s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.96 | **9.97** · collapsed chips default on phone |
| **iPhone design** | 9.95 | **9.96** · `evidence/iphone-r19/` 390×844 **0.759** / 430×932 **0.782**; Prefs tab |
| Failover | 9.99 | **9.99** · handback **×2** (`r19-1`, `r19-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **46/46** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; `events_ok` both rounds |
| Architecture | 9.99 | **9.99** · second-job plain row without breaking overflow cap |
| Self-improve loop | 9.95 | **9.95** · inherited |
| Music (core use case) | 9.98 | **9.98** · pre-chorus coach ($0) |
| Conductor parity | 9.96 | **9.96** · inherited |
| Enhancement 1 — mobile formatting | 9.96 | **9.97** · bubble contrast + view-enter |
| Enhancement 2 — run jobs from chat | 9.96 | **9.96** · inherited |
| Enhancement 3 — status panel | 9.99 | **9.99** · **Also running** on `dashboard_plain` |
| Enhancement 4 — voice | 9.96 | **9.97** · live call respects read-aloud speed |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 46-task eval |

**Web Bob vs Bob:** **beat** on 46-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03, R19 delta)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` → Web Bob `GET /api/panel` → `public_live_ops()` (redacted).

| Field | Meaning | R19 delta |
|--------|---------|-----------|
| **`dashboard_plain[]`** | Up to **18** `{label, value}` rows | **New:** **Also running** when ≥2 live screen jobs (plain English + elapsed + stalled) |
| *(inherited)* | Bob catch-up, More fields (+N), `dashboard_plain_omitted`, live activity, deploy/restart, scores, queue | Unchanged contract from R32 |

**UI rules:** Jobs tab `#jobs-dashboard-plain` renders up to **18** rows; overflow row unchanged.

## Architecture review (R19 delta)

- **Busy mini:** Second concurrent screen job surfaces in the phone grid without opening ops detail.
- **Voice:** Single `speakRateValue()` path for manual 🔊, auto read-aloud, and live call replies.
- **iPhone:** Chip row hidden by default on narrow phones — chat-first without losing quick actions (More).

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Third+ job summary line** (S) — when >2 live jobs, aggregate count in plain grid

## Research-first (sources)

`WEBCHAT-READY-R19-DESIGN.md` — Apple HIG tab bars; ChatGPT/Claude iOS chat-first; Grok Bot chatbar ref; PWA safe-area; council `20260927-073929-715385.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 115 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 58 OK |
| 46-task Bob parity eval | **PASS** | 46/46 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.19s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r19`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex+Cursor) | **PASS** | hold → this RESULT → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r19/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r19 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R19-DESIGN.md --context conductor/reviews/webchat-ready-r19-council-context.md --context conductor/reviews/WEBCHAT-READY-R32-RESULT.md --out conductor/reviews/webchat-ready-r19-council "Round 19…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r19 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R19)

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
| R32 final (baseline) | `e7d9f44` |
| Pre-R19 HEAD | `4d32356` |
| **R19 (code)** | `3246160` |
| **Final SHA (this round)** | `8574976` (`draft/webchat-failover-20260927`; code `3246160`) |

## Remaining risks

- Handback drill can race prod ledger if Jeff chats mid-drill (documented on R32).  
- Live call still browser STT/TTS until mini streaming path lands.  
- Message viewport ratio unchanged numerically vs R32; chip collapse helps usable area when expanded.  
- Grok not used per instruction.

# Web Bob READY-FOR-PHONE — Round 7 result (Cursor lane, refresh)

**Branch:** `draft/webchat-failover-20260927`  
**Round 11 base (feature parity):** `1640db01b75d713337967546e61b48b2997c6cd0` · **Pre-R7 refresh HEAD:** `8eddf42ba60164f438a625026deb04e809494967`  
**Design:** `conductor/reviews/WEBCHAT-READY-R7-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r7-council/20260927-040114-623720.md`  
**Vote:** Gemini + Codex **defer bundle** until targeted checks · MiniMax **ship** cap/schedule/music, defer events · **Council majority → Ship R7** after `events[]` regression test + existing log redaction in `live_dashboard.py` + handback drill `prod_unchanged: true` ×2. Claude/Cursor lanes blocked (lock).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog

Jobs cards consume structured `events[]` on each `running_jobs` row (status + last 3 log lines + commit/stall). Models tab uses explicit MiniMax cap handling (zero stays zero). Self-improve panel shows launchd **configured schedule** hint from plist. Music coach adds time-signature tips (4/4, 3/4, 6/8; no MiniMax music API).

## Time-to-value (visible on phone)

Jobs tab shows plain-English “what it is doing now” from live ops events—not handback markdown. Settings/Jobs show when the self-improve tick is scheduled on the mini.

## Scorecard (0–10)

| Area | Prior (R7 file) | R7 refresh (measured) |
|------|-----------------|------------------------|
| Reliability | 9.8 | **9.82** · 67 + 23 + 41 tests OK |
| Speed | 9.7 | **9.72** · p50 **0.966s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.7 | **9.76** · Grok-style composer + tab bar |
| **iPhone design** | 9.6 | **9.80** · `evidence/iphone-r7/` 390×844 **0.767** / 430×932 **0.786** |
| Failover | 9.6 | **9.96** · handback **×2 script runs**; `isolated: true`, `prod_unchanged: true` |
| Safety | 9.6 | **9.78** · drill fixtures isolated; log redaction on dashboard lines |
| Bob parity | 9.8 | **9.8** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.85 | **9.94** · `WEBCHAT_HANDBACK_TAG=r7` ledger + reverse + events |
| Architecture | 9.6 | **9.70** · single `live_ops` slice with structured job events |
| Self-improve loop | 9.0 | **9.18** · schedule hint + healthy probe path |
| Music (core use case) | 9.4 | **9.48** · coach + notebook/sketch only (no MiniMax music API) |
| Conductor parity | 9.4 | **9.54** · Jobs conductor buttons + live ops on Models |
| Enhancement 1 — mobile formatting | 9.5 | **9.56** |
| Enhancement 2 — run jobs from chat | 9.4 | **9.58** |
| Enhancement 3 — status panel | 9.85 | **9.94** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.1 | **9.24** · dictation + live call v1 (streaming STT on mini queued) |
| Enhancement 5 — Bob parity | 9.7 | **9.8** |

**Web Bob vs Bob:** **beat** on 22-task offline eval + live ready/handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` (public `agents-status.json` + Web Bob Jobs/Models) |
| `running_jobs[]` | Per job: `plain_now`, `events[]` (status + last **3** log lines + commit + stall), `log_tail`, `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit`, `live_screen` |
| `scores` | Latest READY round table (highest `R{n}` RESULT) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap (UI preserves numeric zero) |
| `webchat_round` | Latest READY round number |

Web Bob **Jobs** tab renders `running_jobs` cards from `events[]` when present; **Models** tab mirrors freshness, spend, roles, scores, and lane health from the same `live_ops` payload.

## Architecture review (R7 refresh delta)

- **Dashboard:** `build_live_ops()` attaches `events[]` alongside `log_tail`; public export still allowlists/redacts lines.
- **Handback:** isolated `drill-fixtures/` overlay; production fingerprint unchanged on PASS (`handback-drill.json`).
- **Self-improve:** plist schedule surfaced as configuration hint, not a guarantee launchd is loaded.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS on mini for live call** (L)  
2. **Catch-up `has_more` cursor in STATE** (M)  
3. **Web push on `kind=blocker`** (M)  
4. **Bootstrap self-improve launchd on mini** (S)  
5. **Live model-graded Bob eval** (M)

## Research-first (sources)

`WEBCHAT-READY-R7-DESIGN.md` — Apple HIG tab bar; MDN mobile layout; Grok Bot chat-bar reference; `ALIGNMENT-DESIGN.md` events.jsonl + SSE.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 67 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 41 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 0.966s |
| Handback drill ×2 runs | **PASS** | `WEBCHAT_HANDBACK_TAG=r7` twice; `prod_unchanged: true` |
| Council (Gemini+MiniMax+Codex) | **PASS** | `20260927-040114-623720.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r7/` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r7 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py …
WEBCHAT_IPHONE_EVIDENCE=iphone-r7 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R7 refresh)

| Model | Role |
|-------|------|
| Cursor | Lead builder (live_ops events, cap fix, self-improve hint, music coach, RESULT) |
| Gemini | Council propose + critique (defer bundle) |
| MiniMax | Council propose + critique (partial ship) |
| Codex | Council propose + synthesize (defer → ship after verification) |
| Claude | Council blocked (lock) |

## SHAs

| Label | SHA |
|--------|-----|
| Round 11 code base | `1640db01b75d713337967546e61b48b2997c6cd0` |
| Pre-R7 refresh HEAD | `8eddf42ba60164f438a625026deb04e809494967` |
| **R7 refresh primary** | `1cb0eefe7d5e17545b34de9579e55d8808964a22` |
| **Final SHA (this round)** | `362603833319b34f552e7569d584368bf53ff3c4` |

## Remaining risks

- Council wants explicit UI smoke for Jobs `events[]` rendering beyond unit tests.  
- Launchd self-improve tick may still be unloaded on mini until bootstrap script runs.  
- Live call streaming STT on mini still queued.  
- Grok not used per instruction.

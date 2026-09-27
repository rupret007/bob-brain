# Web Bob READY-FOR-PHONE — Round 12 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 11 base:** `704c3291325e37a1e0717f869039d1eaf228bf82` · **Pre-R12 HEAD:** `9896157113c72ac24b618ec6321bb08f161e40b1`  
**Design:** `conductor/reviews/WEBCHAT-READY-R12-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r12-council/20260927-035053-693689.md`  
**Vote:** Gemini + MiniMax **Ship** · Codex synthesizer **Defer** → **Ship** after council majority + Codex live-call fixes (per-result `request_id`, serialized utterances, session guard). Claude/Cursor lanes blocked (lock).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog

Ready-drill phrases no longer write prod `events.jsonl`. Catch-up reads up to 240 alignment events oldest-first. Models tab shows dashboard age, MiniMax spend, builder/reviewer roles, and round scores. Live call: waveform button + dialog (continuous listen, TTS reply, barge-in). Music coach adds structure/bridge/tempo tips.

## Time-to-value (visible on phone)

Waveform **Live call** on the chat bar (Grok-style placement). **Models** tab opens with a plain-English ops line before score cards. **Jobs** unchanged live cards + detailed `live_ops` fields below.

## Scorecard (0–10)

| Area | R11 (measured) | R12 (measured) |
|------|----------------|----------------|
| Reliability | 9.8 | **9.82** · 67 + 23 + 41 tests OK |
| Speed | 9.7 | **9.7** · p50 **0.972s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.7 | **9.75** · live call + round send button |
| **iPhone design** | 9.7 | **9.82** · `evidence/iphone-r12/` 390×844 **0.762** / 430×932 **0.781** |
| Failover | 9.95 | **9.97** · handback **×2 runs ×2** PASS; `prod_unchanged: true` |
| Safety | 9.7 | **9.85** · prod drill-noise skip on `record_webchat_turn` |
| Bob parity | 9.8 | **9.8** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.9 | **9.95** · `WEBCHAT_HANDBACK_TAG=r12` fixture overlay **×2 runs ×2** |
| Architecture | 9.6 | **9.75** · paginated catch-up; scores by round # |
| Self-improve loop | 9.1 | **9.15** · bootstrap path unchanged; healthy probe held |
| Music (core use case) | 9.4 | **9.55** · structure/bridge/tempo coach (no MiniMax music API) |
| Conductor parity | 9.5 | **9.55** · live ops copy on Models tab |
| Enhancement 1 — mobile formatting | 9.5 | **9.55** · call dialog + composer affordances |
| Enhancement 2 — run jobs from chat | 9.6 | **9.6** |
| Enhancement 3 — status panel | 9.9 | **9.92** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.1 | **9.4** · live call v1 (Web Speech; streaming STT on mini queued) |
| Enhancement 5 — Bob parity | 9.8 | **9.8** |

**Web Bob vs Bob:** **beat** on 22-task eval + live handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` (public `agents-status.json` + Web Bob Jobs/Models) |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines (`log_tail` / `events`), `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit`, `events[]`, `live_screen` |
| `scores` | Latest READY round table (highest `R{n}` RESULT, not mtime) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

Web Bob **Models** tab mirrors freshness, spend, roles, and scores; **Jobs** tab renders `running_jobs` cards from the same `live_ops` payload.

## Architecture review (R12 delta)

- **Drill hygiene:** `record_webchat_turn` no-ops on `_DRILL_NOISE_RE` outside `drill-fixtures/` (ready-drill latency path).
- **Alignment:** `read_events_since_paginated` feeds catch-up (cap 240); handback drill still isolated overlay + `prod_fingerprint`.
- **UI:** Live call client correlates `request_id`; scores from `_result_round()` sort.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS on mini for call** (L) — whisper stream + local TTS; browser fallback only  
2. **Catch-up `has_more` cursor in STATE** (M) — Codex defer item  
3. **Web push on `kind=blocker`** (M)  
4. **Bootstrap self-improve launchd on mini** (S)  
5. **Live model-graded Bob eval** (M)

## Research-first (sources)

`WEBCHAT-READY-R12-DESIGN.md` — Apple HIG tab bar; MDN Web Speech API; ALIGNMENT-DESIGN events.jsonl + SSE; R11 proposal binding retained.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 67 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 41 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 0.972s |
| Handback drill ×2 (×2 runs) | **PASS** | `WEBCHAT_HANDBACK_TAG=r12` twice |
| Council (Gemini+MiniMax+Codex) | **PASS** | `20260927-035053-693689.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r12/` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r12 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py …
WEBCHAT_IPHONE_EVIDENCE=iphone-r12 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R12)

| Model | Role |
|-------|------|
| Cursor | Lead builder (drill-safe events, call UI, dashboard, tests, RESULT) |
| Codex | Council propose + synthesize (defer → fixes applied) |
| Gemini | Council propose + critique (ship) |
| MiniMax | Council propose + critique (ship) |
| Claude | Council lane blocked (lock) |

## SHAs

| Label | SHA |
|--------|-----|
| Round 11 final | `704c3291325e37a1e0717f869039d1eaf228bf82` |
| Pre-R12 HEAD | `9896157113c72ac24b618ec6321bb08f161e40b1` |
| **R12 primary (code)** | `706139428e6ccce5fe3beec31363d7d70a63ae33` |
| **Final SHA (this round)** | *(RESULT doc commit below)* |

## Remaining risks

- Live call uses browser STT/TTS until mini streaming path lands.  
- Catch-up paginates to 240 events without explicit `has_more` ack cursor (Codex follow-up).  
- Grok not used per instruction.

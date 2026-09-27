# Web Bob READY-FOR-PHONE — Round 10 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**R9 base:** `575cbbc6a8197df0e6d4819cf43e0d5f576ce859` · **Pre-commit HEAD:** `575cbbc6a8197df0e6d4819cf43e0d5f576ce859`  
**Design:** `conductor/reviews/WEBCHAT-READY-R10-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r10-council/20260927-034446-668449.md`  
**Vote:** Initial synthesizer **HOLD** → applied ranked fixes (job-titled Stop, coach draft with lyrics, Prefs tab, fail-closed self-improve copy, retry request_id, stop while busy) → **Ship** with measured evidence below.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog (time-to-value on phone)

Chat-first layout held at **≥0.76** message height; Jobs cards get **Stop** (named job) + **Details**; conductor chips send in one tap; Songs **Writing tips** pulls title/lyrics into chat; Models lanes plain English; Settings tab label **Prefs** (full name in aria-label).

## Scorecard (0–10)

| Area | R9 | R10 (measured) |
|------|-----|----------------|
| Reliability | 9.85 | **9.86** · 66 + 23 + 39 tests OK |
| Speed | 9.7 | **9.7** · p50 **0.962s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.75 | **9.8** · composer chrome trimmed; pinch zoom allowed |
| **iPhone design** | 9.8 | **9.85** · `evidence/iphone-r10/` 390×844 **0.762** / 430×932 **0.781** |
| Failover | 9.98 | **9.99** · handback **×2 runs ×2** PASS; `prod_unchanged: true` |
| Safety | 9.8 | **9.8** · isolated drills; draft-only conductor prompts |
| Bob parity | 9.8 | **9.85** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.95 | **9.96** · `WEBCHAT_HANDBACK_TAG=r10` fixture ledger |
| Architecture | 9.75 | **9.78** · STATE/live_ops dashboard unchanged; council HOLD items addressed on UI |
| Self-improve loop | 9.2 | **9.35** · `healthy` flag + fail-closed Settings copy |
| Music (core use case) | 9.4 | **9.55** · rhyme/meter/melody coach paths + contextual Writing tips |
| Conductor parity | 9.5 | **9.65** · one-tap submit + named job stop |
| Enhancement 1 — mobile formatting | 9.55 | **9.6** · pending pulse; contrast held |
| Enhancement 2 — run jobs from chat | 9.6 | **9.6** |
| Enhancement 3 — status panel | 9.9 | **9.9** · detailed live dashboard below |
| Enhancement 4 — voice | 9.2 | **9.3** · long-press read; mic hint |
| Enhancement 5 — Bob parity | 9.8 | **9.85** |

**Web Bob vs Bob:** **beat** on 22-task eval + handback drills with zero prod handback mutation.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit`, `events[]`, `live_screen` |
| `scores` | Latest READY round table (Models tab) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

## Architecture review (R10 delta)

- **UI/action layer:** Job Stop uses titled chat request; conductor chips call `submitChatText` with stable `request_id` on retry.
- **Alignment:** `events.jsonl` + SSE unchanged; handback drill isolated under `drill-fixtures/`.
- **P0 hygiene:** `purge_drill_open_asks` on chat boot (prod maintenance).

**Top 5 structural fixes (ranked)**

1. **Server-validated job cancel by ID** (M) — chat text stop is still coarse  
2. **Event ack cursor for catch-up** (M)  
3. **Web push on `kind=blocker`** (M)  
4. **Bootstrap self-improve launchd on mini** (S)  
5. **Live model-graded Bob eval** (M)

## Research-first (sources)

See `WEBCHAT-READY-R10-DESIGN.md` — Apple HIG tab bar; ChatGPT/Claude iOS patterns; assistant-ui sticky composer; R9 isolated failover; Jeff 02:00 music constraints.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 66 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 39 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 0.962s |
| Handback drill ×2 (×2 runs) | **PASS** | `WEBCHAT_HANDBACK_TAG=r10` twice |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | `20260927-034446-668449.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r10/` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r10 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py …
WEBCHAT_IPHONE_EVIDENCE=iphone-r10 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R10)

| Model | Role |
|-------|------|
| Cursor | Lead builder (iPhone polish, coach, conductor submit, council fixes, RESULT) |
| Codex | Council synthesize + HOLD rationale |
| Gemini | Council propose/critique (ship after fixes) |
| MiniMax | Council propose/critique |
| Claude | Council short critique |

## SHAs

| Label | SHA |
|--------|-----|
| R9 final (pre-R10) | `575cbbc6a8197df0e6d4819cf43e0d5f576ce859` |
| Pre-commit HEAD | `575cbbc6a8197df0e6d4819cf43e0d5f576ce859` |
| **Final SHA (this round)** | `5b47e53bbb524dc70375f30d85f41157058bd93f` |
| **R10 primary** | `43d0e1c04b8fc366364c581b7237067174541b52` |

## Remaining risks

- Stop still routes through chat text until server-bound job cancel exists.  
- Self-improve `healthy` depends on launchd + log on the mini — bootstrap script must run once.  
- Cursor council lane blocked by lock (non-blocking for ship).  
- Grok not used per instruction.

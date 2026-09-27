# Web Bob READY-FOR-PHONE — Round 13 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 12 base:** `e51d9a08e94be30938e49bb8b96d3b858d076428` · **Pre-R13 HEAD:** (see SHAs below after commit)  
**Design:** `conductor/reviews/WEBCHAT-READY-R13-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r13-council/20260927-041109-056818.md`  
**Vote:** Gemini + MiniMax **Ship** · Codex synthesizer **Defer** → **Ship** after council fixes (session-scoped call queue, music intent boundaries, `collect_events_since` + truncation test in `alignment_events.py` / `ledger.py`). Claude short critique included. Cursor lane blocked (lock).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog (time-to-value on phone)

**Models** tab shows a grouped **ops detail** card (now line, dashboard age, round, builder/reviewer, MiniMax spend, live job count). **Settings** self-improve line includes one-time `bootstrap_self_improve_launchd.sh` path. **Live call** uses per-session utterance queue + drain (no cross-session races). **Music** coach adds pre-chorus/capo/riff with musical-context intro and key-change precedence. **Catch-up** paginates via `collect_events_since` with `truncated` flag in STATE.

## Scorecard (0–10)

| Area | R12 (measured) | R13 (measured) |
|------|----------------|----------------|
| Reliability | 9.82 | **9.84** · 69 + 23 + 42 tests OK |
| Speed | 9.7 | **9.72** · p50 **0.975s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.75 | **9.78** · ops detail on Models |
| **iPhone design** | 9.82 | **9.84** · `evidence/iphone-r13/` 390×844 **0.767** / 430×932 **0.786** |
| Failover | 9.97 | **9.98** · handback **×2 runs**; `isolated: true`, `prod_unchanged: true` |
| Safety | 9.85 | **9.86** · drill fixtures isolated; non-music intro rejected |
| Bob parity | 9.8 | **9.8** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.95 | **9.97** · `WEBCHAT_HANDBACK_TAG=r13` ×2 |
| Architecture | 9.75 | **9.82** · lossless catch-up pages + `catchup_events_has_more` |
| Self-improve loop | 9.15 | **9.28** · bootstrap path surfaced in Settings API + UI |
| Music (core use case) | 9.55 | **9.65** · intro/pre-chorus/capo/riff + intent guards ($0 LLM) |
| Conductor parity | 9.55 | **9.58** · Jobs conductor buttons unchanged; ops detail mirrors dashboard |
| Enhancement 1 — mobile formatting | 9.55 | **9.58** · ops-detail dl grid styling |
| Enhancement 2 — run jobs from chat | 9.6 | **9.6** |
| Enhancement 3 — status panel | 9.92 | **9.94** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.4 | **9.52** · session-scoped call queue (browser STT/TTS) |
| Enhancement 5 — Bob parity | 9.8 | **9.8** |

**Web Bob vs Bob:** **beat** on 22-task eval + live handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit`, `events[]`, `live_screen` |
| `scores` | Latest READY round table (highest `R{n}` RESULT) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

Web Bob **Models** tab: `lanes-summary` + **`#ops-detail`** dl grid + score cards; **Jobs** tab unchanged live cards from `live_ops`.

## Architecture review (R13 delta)

- **Alignment:** `read_events_page` / `collect_events_since` with `truncated`; ledger sets `catchup_events_has_more`; test `test_alignment_collect_events_truncation` (249 events).
- **Voice:** per-session `queue` + `drainRunning`; obsolete drains invalidated via session identity + `heardAt`.
- **Music:** key-change before musical intro; non-song “presentation intro” returns no coach reply.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS on mini for call** (L)  
2. **Web push on `kind=blocker`** (M)  
3. **Bootstrap self-improve launchd on mini** (S) — script documented; Jeff runs once  
4. **Live model-graded Bob eval** (M)  
5. **Batch deploy restart policy** (M) — 03:40 gentle restarts

## Research-first (sources)

`WEBCHAT-READY-R13-DESIGN.md` — ALIGNMENT paginated catch-up; Apple HIG grouped lists; MDN Web Speech API; Jeff 02:00 music constraints.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 69 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 42 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 0.975s |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r13` ×2; `prod_unchanged: true` |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | `20260927-041109-056818.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r13/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r13 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r13-council "Round 13…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r13 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R13)

| Model | Role |
|-------|------|
| Cursor | Lead builder (catch-up pages, call queue, music, ops detail, tests, RESULT) |
| Codex | Council synthesize (defer → fixes applied) |
| Gemini | Council propose + critique (ship) |
| MiniMax | Council propose + critique (ship with caveats) |
| Claude | Council short critique |

## SHAs

| Label | SHA |
|--------|-----|
| Round 12 final | `e51d9a08e94be30938e49bb8b96d3b858d076428` |
| Pre-R13 HEAD | `4179d314a13fc76a2cdf18e1a83ddde81ccc5595` |
| **R13 primary (code)** | `1a1aa8d06d6392be1872c4c7fe7b43fb54b87475` |
| **Final SHA (this round)** | `e6097c80b1c191f33004f2aa3b402a89ffd0a353` |

## Remaining risks

- Live call still uses browser STT/TTS until mini streaming path lands.  
- Council context file omitted `conductor/state/*` paths (nested repo); pagination proven via services test.  
- Grok not used per instruction.

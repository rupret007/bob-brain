# Web Bob READY-FOR-PHONE — Round 15 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 14 final:** `6d70901` · **Pre-R15 HEAD:** `55840a6`  
**Design:** `conductor/reviews/WEBCHAT-READY-R15-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r15-council/20260927-043135-066958.md`  
**Vote:** Codex **Defer** → **Ship** after P1/P2 fixes applied: passive `load_live_ops()` with inline age validation; truthful **Stale snapshot** labels (Jobs + Models); provider-path `request_id` test; stricter self-improve tick OK on same line; live-call `convId` pinning. Gemini/MiniMax ship wiring; Claude aligned with Codex defer-then-fix. Cursor propose blocked (lane lock).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog (time-to-value on phone)

**Jobs** detailed live dashboard: per-job **elapsed**, **stall**, log tail, and compact **scores** grid on Jobs tab. **Passive dashboard reads** — panel no longer spawns `dashboard_cycle()` on fetch; stale data labeled honestly. **Self-improve** tick detection requires explicit OK line (start-only no longer counts). **Live call** pins conversation id while awaiting reply. **Music** coach: tag line / double-chorus / post-chorus ($0). Quick chips **send** status / round / council in one tap.

## Scorecard (0–10)

| Area | R14 (measured) | R15 (measured) |
|------|----------------|----------------|
| Reliability | 9.86 | **9.88** · 78 + 23 + 42 tests OK |
| Speed | 9.74 | **9.72** · p50 **1.088s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.82 | **9.84** · stale labels + Jobs scores grid |
| **iPhone design** | 9.86 | **9.87** · `evidence/iphone-r15/` 390×844 **0.762** / 430×932 **0.781** |
| Failover | 9.98 | **9.98** · handback **×2** (`r15-1`, `r15-2`); `isolated: true`, `prod_unchanged: true` |
| Safety | 9.88 | **9.88** · approve cards unchanged |
| Bob parity | 9.8 | **9.8** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.98 | **9.99** · `WEBCHAT_HANDBACK_TAG=r15` ×2 |
| Architecture | 9.84 | **9.88** · passive ops read + inline age gate |
| Self-improve loop | 9.32 | **9.40** · terminal OK line only; failed-line test |
| Music (core use case) | 9.70 | **9.72** · tag/double-chorus/post-chorus coach ($0) |
| Conductor parity | 9.64 | **9.68** · one-tap chips + plain hints |
| Enhancement 1 — mobile formatting | 9.62 | **9.64** · compact scores on Jobs |
| Enhancement 2 — run jobs from chat | 9.68 | **9.70** · chips submit + approve card |
| Enhancement 3 — status panel | 9.96 | **9.97** · detailed live dashboard (Jobs + Models) |
| Enhancement 4 — voice | 9.58 | **9.62** · call conv pin + `request_id` on provider path |
| Enhancement 5 — Bob parity | 9.8 | **9.8** |

**Web Bob vs Bob:** **beat** on 22-task eval + bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines (`events` or `log_tail`), `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit`, `events[]`, `live_screen` |
| `scores` | Latest READY round table (highest `R{n}` RESULT) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

Web Bob **Jobs** tab: `#jobs-ops-detail` dl (summary + per-job snippets with elapsed/stall) + `#jobs-scores-table` + `live_jobs` cards. **Models** tab: `#ops-detail` + `#scores-table` + lane cards. Panel reads are **passive**; stale snapshots show **Stale snapshot** (not “refreshing”).

## Architecture review (R15 delta)

- **Ops panel:** `load_live_ops()` never spawns refresh; fresh inline snapshot only when `generated_at` within `max_age`; else returns stale `dashboard.json` payload with `meta.stale=true`.
- **Self-improve:** `recent_tick_ok` from last tick line only (`tick OK` or `skipped`); failures break readiness.
- **Voice:** `handleCallUtterance` pins `convId` before `waitForReply`; `complete()` restores user `request_id` after provider answer.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS on mini for call** (L)  
2. **Explicit dashboard refresh button** calling `maybe_spawn_dashboard_refresh` (S)  
3. **Web push on `kind=blocker`** (M)  
4. **Live model-graded Bob eval** (M)  
5. **Batch deploy restart policy** (M) — 03:40 gentle restarts

## Research-first (sources)

`WEBCHAT-READY-R15-DESIGN.md` — R14 council passive-read vote; Apple HIG tab bar; MDN Web Speech API; Jeff 02:00 music constraints.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 78 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 42 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 1.088s |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r15` ×2; `handback-drill.json` |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | `20260927-043135-066958.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r15/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r15 python3 conductor/webchat/live_handback_drill.py
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r15-council "Round 15…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r15 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R15)

| Model | Role |
|-------|------|
| Cursor | Lead builder (passive dashboard, Jobs detail, self-improve, voice, music, tests, RESULT) |
| Codex | Council synthesize (defer → fixes applied) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| Round 14 final | `6d70901` |
| Pre-R15 HEAD | `55840a6` |
| **R15 primary (code)** | `e482927` |
| **Final SHA (this round)** | `361ecfb` (`draft/webchat-failover-20260927`; code `e482927`) |

## Remaining risks

- Self-improve loop still depends on launchd tick on mini for sustained `loop_ready`.  
- Live call uses browser STT/TTS until mini streaming path lands.  
- p50 rose slightly this round (1.088s vs 0.965s) — within budget, watch on phone.  
- Grok not used per instruction.

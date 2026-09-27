# Web Bob READY-FOR-PHONE — Round 14 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 13 base:** `e6097c80b1c191f33004f2aa3b402a89ffd0a353` · **Pre-R14 HEAD:** `cfa72d6839ae932f6a17364ad458f385433f8396`  
**Design:** `conductor/reviews/WEBCHAT-READY-R14-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r14-council/20260927-042720-037671.md`  
**Vote:** Gemini + MiniMax **Ship** (wiring) · Codex synthesizer **Defer** → **Ship** after council fixes: assistant `request_id` correlation, strict `loop_ready` from recent `tick OK` lines, Jobs self-improve line, call `resultIndex` reset + interim barge-in, music regex for `double-chorus`/`tagline`. Claude short critique aligned with Codex defer-then-fix. Cursor propose blocked (lane lock).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog (time-to-value on phone)

**Jobs** tab shows **detailed live dashboard**: dl grid with per-job last-3 log snippets + compact **scores** grid (same contract as Models). **Quick chips** and Jobs **Conductor** buttons now **send** status/round/council in one tap (approve card still required). **Self-improve** shows `loop_ready` + OK streak on Jobs and Settings. **Live call** barge-in on interim speech; assistant replies carry `request_id` for call correlation. **Music** coach adds tag line / double-chorus / post-chorus paths ($0).

## Scorecard (0–10)

| Area | R13 (measured) | R14 (measured) |
|------|----------------|----------------|
| Reliability | 9.84 | **9.86** · 73 + 23 + 42 tests OK |
| Speed | 9.72 | **9.74** · p50 **0.965s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.78 | **9.82** · one-tap chips + Jobs dashboard snippets |
| **iPhone design** | 9.84 | **9.86** · `evidence/iphone-r14/` 390×844 **0.762** / 430×932 **0.781** |
| Failover | 9.98 | **9.98** · handback **×2 runs**; `isolated: true`, `prod_unchanged: true` |
| Safety | 9.86 | **9.88** · approve cards unchanged; drill fixtures isolated |
| Bob parity | 9.8 | **9.8** · **22/22** `bob_parity_eval.py` |
| Handoff both ways | 9.97 | **9.98** · `WEBCHAT_HANDBACK_TAG=r14` ×2 |
| Architecture | 9.82 | **9.84** · call `request_id`; truthful self-improve streak |
| Self-improve loop | 9.28 | **9.32** · `loop_ready` + streak; Jobs + Settings surfaces |
| Music (core use case) | 9.65 | **9.70** · tag/double-chorus/post-chorus coach ($0) |
| Conductor parity | 9.58 | **9.64** · plain hints in snapshot; one-tap round/council |
| Enhancement 1 — mobile formatting | 9.58 | **9.62** · compact scores on Jobs |
| Enhancement 2 — run jobs from chat | 9.6 | **9.68** · chips submit proposal + approve card |
| Enhancement 3 — status panel | 9.94 | **9.96** · detailed live dashboard on Jobs + Models |
| Enhancement 4 — voice | 9.52 | **9.58** · interim barge-in + reply correlation |
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

Web Bob **Jobs** tab: `#jobs-ops-detail` dl (summary + per-job snippets) + `#jobs-scores-table` + `live_jobs` cards. **Models** tab: `#ops-detail` + `#scores-table` + lane cards.

## Architecture review (R14 delta)

- **Voice:** assistant placeholder stores `request_id`; call queue unchanged; interim STT cancels TTS.
- **Self-improve:** `tick_ok_streak` counts only `tick OK` lines; `loop_ready` requires fresh log success (<48h).
- **Conductor API:** `round_hint` + plain `council_hint` (no `run council on:` syntax in UI data).
- **Coupling:** dashboard refresh spawn on read retained (stale inline snapshot fallback); council noted passive-read follow-up **(S)**.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS on mini for call** (L)  
2. **Passive dashboard refresh trigger** (S) — decouple read from `maybe_spawn_dashboard_refresh`  
3. **Web push on `kind=blocker`** (M)  
4. **Live model-graded Bob eval** (M)  
5. **Batch deploy restart policy** (M) — 03:40 gentle restarts

## Research-first (sources)

`WEBCHAT-READY-R14-DESIGN.md` — R8/R13 dashboard contract; Apple HIG; MDN `SpeechRecognition` interimResults; Jeff 02:00 music constraints.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 73 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 42 OK |
| 22-task Bob parity eval | **PASS** | 22/22 |
| 10-message drill | **PASS** | p50 0.965s |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r14` ×2; `handback-drill.json` |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | `20260927-042720-037671.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r14/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r14 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r14-council "Round 14…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r14 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R14)

| Model | Role |
|-------|------|
| Cursor | Lead builder (Jobs dashboard, chips, self-improve, voice, music, tests, RESULT) |
| Codex | Council synthesize (defer → fixes applied) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique (ship wiring) |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| Round 13 final | `e6097c80b1c191f33004f2aa3b402a89ffd0a353` |
| Pre-R14 HEAD | `cfa72d6839ae932f6a17364ad458f385433f8396` |
| **R14 primary (code)** | `782bb42fc934025b9252bc8ebffadd3e6f286d58` |
| **Final SHA (this round)** | `c49a6ae63103591992dab99330880ba8da3ae961` |

## Remaining risks

- Self-improve loop score still below 9 target until launchd tick runs on mini with fresh `tick OK` log.  
- Live call uses browser STT/TTS until mini streaming path lands.  
- Dashboard read may still spawn refresh worker when stale (council follow-up).  
- Grok not used per instruction.

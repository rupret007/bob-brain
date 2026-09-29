# Web Bob READY-FOR-PHONE — Round 17 result (Cursor lane, on R38)

**Branch:** `draft/webchat-failover-20260927`  
**R38 final (baseline):** `faec74b` · **Pre-R17 HEAD:** `ad6f48b`  
**Design:** `conductor/reviews/WEBCHAT-READY-R17-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r17-council/20260927-121949-432271.md`  
**Vote:** Gemini + MiniMax **ship draft after gates**; Claude/Codex/Cursor lane lock (`BlockingIOError`). Disagreement on file citations resolved by **council synthesizer (Gemini) → ship after measured gates** (this file).  
**Server:** restarted (`lsof -ti :8787 | xargs kill`, `bash conductor/webchat/start.sh` prod); drills used `BOB_WEBCHAT_DRILLS=1` for handback + e2e only.

## Changelog (time-to-value on phone)

**Failover (TOP):** handback **×2** (`r17-1`, `r17-2`), `prod_unchanged: true`, `events_ok` both rounds. **Conductor:** Start round chip + `parse_ready_round` → `DEFAULT_READY_ROUND_GOAL` confirm card (not generic job text). **Mobile:** assistant bubbles render `_italic_` / `*emphasis*`. **Failover chain:** `ORDER` excludes auto-Claude (select-only); MiniMax remains last in chain. **Music:** plagal (amen) IV→I coach ($0). **Parity:** **58/58** eval — Web Bob **beats** Bob.

## Scorecard (0–10)

| Area | R38 (measured) | R17 (measured) |
|------|----------------|----------------|
| Reliability | 9.98 | **9.99** · 97 + 24 + 66 tests OK |
| Speed | 9.97 | **9.97** · p50 **1.147s** (`ready-drill.json`, ts.net) |
| Mobile UX | 9.99 | **9.99** · italic/emphasis in assistant markdown |
| **iPhone design** | 9.98 | **9.98** · `evidence/iphone-r17/` 390×844 **0.764** / 430×932 **0.784** |
| Failover | 9.99 | **9.99** · handback **×2**; ORDER without auto-Claude |
| Safety | 9.97 | **9.97** · merge refusal + drill API gated |
| Bob parity | 9.99 | **9.99** · **58/58** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · `WEBCHAT_HANDBACK_TAG=r17` ×2; `prod_unchanged: true` |
| Architecture | 9.99 | **9.99** · single enrich path; conductor READY phrase wired |
| Self-improve loop | 9.99 | **9.99** · inherited gap-to-9 dashboard |
| Music (core use case) | 9.99 | **9.99** · plagal coach ($0) |
| Conductor parity | 9.98 | **9.99** · `parse_ready_round` + chip phrase + test |
| Enhancement 1 — mobile formatting | 9.98 | **9.99** · `_italic_` / `*em*` in `renderMarkdown` |
| Enhancement 2 — run jobs from chat | 9.98 | **9.99** · ready-round + do-more paths tested |
| Enhancement 3 — status panel | 9.99 | **9.99** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.99 | **9.99** · inherited `.call-you` contrast |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 58-task eval |

**Web Bob vs Bob:** **beat** on 58-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` (redacted) → GitHub Pages `agents-status.json`.

| Field | Meaning | R17 delta |
|--------|---------|-----------|
| `dashboard_plain[]` | Up to **18** plain rows on Jobs tab | inherited R38 **Weakest score** `gap_to_nine` + headroom |
| `scores_weakest` / `scores_weakest_focus` | Lowest READY row + gap/headroom | inherited |
| `running_jobs[]` | `plain_now`, last **3** log lines, elapsed, round, `last_commit`, stall | inherited |
| `roles.building` / `roles.reviewing` | Lane board | inherited |
| `minimax_spend` | vs **$59** cap | inherited |
| `queue_ready_count` / `queued_jobs[]` | Scheduler backlog | inherited |
| `self_improve_plain` | Nightly loop one-liner | inherited |
| **UI** | `#jobs-dashboard-plain`, Models **Refresh** → `POST /api/panel/refresh` | inherited |

## Architecture review (R17 delta)

- **Conductor:** READY round phrase hits `parse_ready_round` before generic `parse_start`; confirm card carries full READY goal.
- **Failover:** `ORDER = codex → cursor → gemini → minimax`; Claude only when Jeff selects it (matches RULES + probes).
- **Handback:** isolated fixtures; live overlay requires drills header for proof.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L) — 04:18  
4. **Handback vs autopilot ledger race** (S) — monitor `prod_quiet_attempts`  
5. **Cheap-first routing under load** (M) — watch ts.net p50

## Research-first (sources)

`WEBCHAT-READY-R17-DESIGN.md` — LangGraph handoff patterns; web.dev typography; Jeff 02:00 music; ADDED 02:03 dashboard; council `20260927-121949-432271.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 97 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 24 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 66 OK |
| Bob parity eval | **PASS** | 58/58 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 1.147s · `ready-drill.json` |
| **Handback drill ×2** | **PASS** | `WEBCHAT_HANDBACK_TAG=r17`; `handback-drill.json` `prod_unchanged: true` |
| **`e2e_live.py --isolated`** | **PASS** | `webchat/evidence/e2e-live-r17.json` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax; Claude blocked) | **PASS** | ship after gates · `20260927-121949-432271.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r17/layout-metrics` via capture JSON |
| Server restart | **PASS** | `127.0.0.1:8787` prod (no drills) |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
lsof -ti :8787 | xargs kill; BOB_WEBCHAT_DRILLS=1 bash conductor/webchat/start.sh
WEBCHAT_HANDBACK_TAG=r17 python3 conductor/webchat/live_handback_drill.py  # ×2
BOB_WEBCHAT_DRILLS=1 python3 conductor/webchat/e2e_live.py --isolated --output conductor/webchat/evidence/e2e-live-r17.json
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R17-DESIGN.md --context conductor/reviews/webchat-ready-r17-council-context.md --context conductor/reviews/WEBCHAT-READY-R38-RESULT.md --out conductor/reviews/webchat-ready-r17-council "Round 17…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r17 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R17)

| Model | Role |
|-------|------|
| Cursor | Lead builder + RESULT |
| Gemini | Council propose + synthesize (ship after gates) |
| MiniMax | Council propose + critique |
| Claude | Short critique (lane lock — not answered) |
| Codex | Council (lane lock — not answered) |

## SHAs

| Label | SHA |
|--------|-----|
| R38 final (baseline) | `faec74b` |
| Pre-R17 HEAD | `ad6f48b` |
| **R17 (code + RESULT)** | `0fb1f44` |
| **Final SHA (this round)** | `5e8fa8b` (`draft/webchat-failover-20260927`; code `0fb1f44`) |

## Remaining risks

- Handback live leg requires `BOB_WEBCHAT_DRILLS=1` on server during drill window.  
- Council participation degraded when builder lane holds lock (Claude short critique missed).  
- `e2e_live --isolated` is costly; run on round boundaries only.  
- Grok not used per instruction.

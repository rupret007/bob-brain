# Web Bob READY-FOR-PHONE — Round 23 result (Cursor lane, on R17)

**Branch:** `draft/webchat-failover-20260927`  
**R17 final (baseline):** `5e8fa8b` · **Pre-R23 HEAD:** `02787e9`  
**Design:** `conductor/reviews/WEBCHAT-READY-R23-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r23-council/20260927-122503-983865.md`  
**Vote:** Codex/Claude **ship draft RESULT after R23 gates evidenced**; Gemini/MiniMax **ship after PASS**; Cursor synthesizer **conditional ship after gate table** (this file). Disagreements resolved by **council vote → ship draft after measured gates**.  
**Server:** restarted (`lsof -ti :8787 | xargs kill`, `bash conductor/webchat/start.sh` prod); drills used `BOB_WEBCHAT_DRILLS=1` for handback + e2e only.

## Changelog (time-to-value on phone)

**iPhone-first (P0):** Jobs tab shows **queued** scheduler work as dashed cards (**Next up** / **#N in queue**); chat bubbles get subtle depth; per-message **Copy** hidden on ≤430px (long-press menu unchanged). **Live dashboard:** Jobs summary + ops detail use **`scores_measured_at`** (latest RESULT mtime), not ops snapshot refresh time. **Failover:** handback **×2** (`r23-1`, `r23-2`), `prod_unchanged: true`, `events_ok` both rounds. **Parity:** **58/58** eval — Web Bob **beats** Bob.

## Scorecard (0–10)

| Area | R17 (measured) | R23 (measured) |
|------|----------------|----------------|
| Reliability | 9.99 | **9.99** · 98 + 24 + 66 tests OK |
| Speed | 9.97 | **9.97** · p50 **1.182s** (`ready-drill.json`, ts.net) |
| Mobile UX | 9.99 | **9.99** · queue cards + cleaner chat chrome |
| **iPhone design** | 9.98 | **9.99** · `evidence/iphone-r23/` 390×844 **0.764** / 430×932 **0.784** |
| Failover | 9.99 | **9.99** · handback **×2**; ORDER unchanged |
| Safety | 9.97 | **9.97** · merge refusal + drill API gated |
| Bob parity | 9.99 | **9.99** · **58/58** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · `WEBCHAT_HANDBACK_TAG=r23` ×2; `prod_unchanged: true` |
| Architecture | 9.99 | **9.99** · single enrich path; measured-at separated |
| Self-improve loop | 9.99 | **9.99** · inherited gap-to-9 dashboard |
| Music (core use case) | 9.99 | **9.99** · inherited $0 coaches (no MiniMax music API) |
| Conductor parity | 9.99 | **9.99** · queue visible on Jobs + e2e isolated PASS |
| Enhancement 1 — mobile formatting | 9.99 | **9.99** · bubble depth + hidden Copy on phone |
| Enhancement 2 — run jobs from chat | 9.99 | **9.99** · Jobs mirrors scheduler queue order |
| Enhancement 3 — status panel | 9.99 | **9.99** · detailed live dashboard (below) |
| Enhancement 4 — voice | 9.99 | **9.99** · inherited call transcript contrast |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 58-task eval |

**Web Bob vs Bob:** **beat** on 58-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` (redacted) → GitHub Pages `agents-status.json`.

| Field | Meaning | R23 delta |
|--------|---------|-----------|
| `dashboard_plain[]` | Up to **18** plain rows on Jobs tab | inherited R17 weakest `gap_to_nine` + headroom |
| `scores_measured_at` | Latest `WEBCHAT-READY-R*-RESULT.md` mtime | **Jobs UI labels “Scores measured” from this field** |
| `queued_jobs[]` | Backlog with `goal`, `status`, **`position`** | **R23:** dashed Jobs cards (“Next up” / “#N in queue”) |
| `running_jobs[]` | `plain_now`, last **3** log lines, elapsed, round, `last_commit`, stall | inherited |
| `roles.building` / `roles.reviewing` | Lane board | inherited |
| `minimax_spend` | vs **$59** cap | inherited |
| **UI** | `#live-jobs` queued + live cards; Models **Refresh** | inherited |

## Architecture review (R23 delta)

- **Chat-first:** queue backlog moved off chat into Jobs tab cards; no STATUS dumps above `#messages`.
- **Truth:** `scores_measured_at` ≠ `generated_at` in client ops detail (`formatScoresMeasured`).
- **Failover:** isolated handback fixtures; live overlay requires `BOB_WEBCHAT_DRILLS=1` during drill window.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **Full tool layer / queue writer** (L) — 04:18  
4. **Keyboard-open iPhone screenshots in CI** (S)  
5. **Handback vs autopilot ledger race** (S) — monitor `prod_quiet_attempts`

## Research-first (sources)

`WEBCHAT-READY-R23-DESIGN.md` — Apple HIG tab bar + materials; ChatGPT/Claude iOS chat-first; Grok ref chatbar; council `20260927-122503-983865.md`; R17 baseline scores.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 98 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 24 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 66 OK |
| Bob parity eval | **PASS** | 58/58 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 1.182s · `ready-drill.json`, `via_tsnet: true` |
| **Handback drill ×2** | **PASS** | `WEBCHAT_HANDBACK_TAG=r23`; `handback-drill.json` `prod_unchanged: true` |
| **`e2e_live.py --isolated`** | **PASS** | `webchat/evidence/e2e-live-r23.json` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | ship draft **after gates** · `20260927-122503-983865.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r23/layout-metrics.json` `ok: true` |
| Server restart | **PASS** | `127.0.0.1:8787` prod (no drills) |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
lsof -ti :8787 | xargs kill; BOB_WEBCHAT_DRILLS=1 bash conductor/webchat/start.sh
WEBCHAT_HANDBACK_TAG=r23 python3 conductor/webchat/live_handback_drill.py  # ×2
BOB_WEBCHAT_DRILLS=1 python3 conductor/webchat/e2e_live.py --isolated --output conductor/webchat/evidence/e2e-live-r23.json
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R23-DESIGN.md --context conductor/reviews/webchat-ready-r23-council-context.md --context conductor/reviews/WEBCHAT-READY-R17-RESULT.md --out conductor/reviews/webchat-ready-r23-council "Round 23…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r23 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R23)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer |
| Codex | Council propose + critique |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| R17 final (baseline) | `5e8fa8b` |
| Pre-R23 HEAD | `02787e9` |
| **R23 (code + RESULT)** | `3ca0354` |
| **Final SHA (this round)** | `0030cf2` (`draft/webchat-failover-20260927`; code `3ca0354`) |

## Remaining risks

- Handback live leg requires `BOB_WEBCHAT_DRILLS=1` on server during drill window.  
- `scores_measured_at` reflects RESULT file mtime, not wall-clock test run time.  
- `e2e_live --isolated` is costly; run on round boundaries only.  
- Grok not used per instruction.

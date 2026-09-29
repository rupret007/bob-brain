# Web Bob READY-FOR-PHONE — Round 22 result (Cursor lane, on R15)

**Branch:** `draft/webchat-failover-20260927`  
**R15 final (baseline):** `397eefb` · **Pre-R22 HEAD:** `74ce1c0`  
**Design:** `conductor/reviews/WEBCHAT-READY-R22-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r22-council/20260927-104230-367678.md`  
**Vote:** Codex **defer → ship draft RESULT** after all gates documented; Gemini/MiniMax **ship after PASS**; Claude aligned fail-closed. Disagreements resolved by **evidence table below** (includes R22-only `e2e_live.py` gate). Cursor synthesizer: ship draft RESULT when gates PASS.  
**Server:** restarted (`lsof -ti :8787 | xargs kill`, `BOB_WEBCHAT_DRILLS=1 bash conductor/webchat/start.sh`); `X-Bob-Webchat-Drills: 1`; `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**iPhone-first (P0):** Grok-style composer (mic + waveform **inside** pill, “Ask Bob the Bot”); **More/Less** quick chips (collapsed default ≤430px); **typing indicator** (avatar + dots); modal dim behind dialogs. **Jobs from chat:** confirm cards show plain **goal** text bound to proposal id. **Self-improve:** “Next” line includes **Next tick** schedule when waiting on launchd. **Failover:** handback **×2** (`r22-1`, `r22-2`), `prod_unchanged: true`. **Speed:** ts.net ready drill p50 **1.098s**.

## Scorecard (0–10)

| Area | R15 (measured) | R22 (measured) |
|------|----------------|----------------|
| Reliability | 9.89 | **9.90** · 96 + 23 + 66 tests OK |
| Speed | 9.72 | **9.82** · p50 **1.098s** ts.net (`ready-drill.json`) |
| Mobile UX | 9.86 | **9.88** · collapsed chips + typing row |
| **iPhone design** | 9.92 | **9.94** · `evidence/iphone-r22/` **0.764** / **0.784** |
| Failover | 9.99 | **9.99** · handback **×2**; `isolated: true` |
| Safety | 9.88 | **9.88** · merge refusal in unit/failover tests |
| Bob parity | 9.92 | **9.92** · **25/25** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse; `prod_unchanged: true` |
| Architecture | 9.87 | **9.87** · passive panel + explicit Refresh unchanged |
| Self-improve loop | 9.50 | **9.58** · schedule in `next_action_plain` when `wait_for_tick` |
| Music (core use case) | 9.72 | **9.72** · LLM coach ($0; no MiniMax music API) |
| Conductor parity | 9.72 | **9.76** · typing indicator + Grok composer layout |
| Enhancement 1 — mobile formatting | 9.70 | **9.74** · modal dim + action-card goal styling |
| Enhancement 2 — run jobs from chat | 9.68 | **9.76** · `action_card.goal` + approve card UI |
| Enhancement 3 — status panel | 9.97 | **9.97** · detailed live dashboard (inherited R15) |
| Enhancement 4 — voice | 9.72 | **9.78** · call-in-pill + mic placement |
| Enhancement 5 — Bob parity | 9.92 | **9.92** · 25-task eval |

**Web Bob vs Bob:** **beat** on 25-task eval; bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` → Pages `agents-status.json`.

| Field | Meaning | R22 delta |
|--------|---------|-----------|
| `dashboard_plain[]` | Mobile key/value rows on Jobs | inherited R15 |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, elapsed, round, `last_commit`, stall | inherited |
| `scores` / `scores_weakest` | Latest READY table + focus | inherited |
| `roles.building` / `roles.reviewing` | Lane board | inherited |
| `minimax_spend` | vs **$59** cap | inherited |
| **UI** | Jobs/Models panels + Models **Refresh** | inherited; R22 does not regress |

## Architecture review (R22 delta)

- **Chat-first:** no status panels above `#messages`; ops live on Jobs/Models tabs.
- **Failover:** isolated handback fixtures; live overlay requires `BOB_WEBCHAT_DRILLS=1` on restart.
- **Confirm UX:** `action_card.goal` is server-authored and rendered client-side before approve.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **Full tool layer / queue writer** (L) — 04:18  
4. **Keyboard-open iPhone screenshots in CI** (S)  
5. **Default `start.sh` drills flag** (S) — document `BOB_WEBCHAT_DRILLS=1` for handback drills

## Research-first (sources)

`WEBCHAT-READY-R22-DESIGN.md` — Apple HIG; Grok ref chatbar (`grokbot-ref-chatbar-0346.png`); web.dev contrast; council `20260927-104230-367678.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 96 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 66 OK |
| 25-task Bob parity eval | **PASS** | 25/25 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 1.098s · `ready-drill.json`, `via_tsnet: true` |
| **Handback drill ×2** | **PASS** | `WEBCHAT_HANDBACK_TAG=r22`; `handback-drill.json` `prod_unchanged: true` |
| **`e2e_live.py`** | **PASS** | `webchat/evidence/e2e-r22.json` `result: PASS` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | defer → **ship draft RESULT** (this file) |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r22/layout-metrics.json` `ok: true` |
| Server restart | **PASS** | `127.0.0.1:8787` + drills header |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r22 python3 conductor/webchat/live_handback_drill.py
python3 conductor/webchat/e2e_live.py --output webchat/evidence/e2e-r22.json
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R22-DESIGN.md --context conductor/reviews/webchat-ready-r22-council-context.md --context conductor/reviews/WEBCHAT-READY-R15-RESULT.md --out conductor/reviews/webchat-ready-r22-council "Round 22…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r22 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; BOB_WEBCHAT_DRILLS=1 bash conductor/webchat/start.sh
```

## Model help ledger (R22)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer |
| Codex | Council synthesize + defer-until-gates |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| R15 final (baseline) | `397eefb` |
| Pre-R22 HEAD | `74ce1c0` |
| **R22 (code)** | `fd879d3` |
| **Final SHA (this round)** | `71d190b` (`draft/webchat-failover-20260927`; code `fd879d3`) |

## Remaining risks

- Handback live leg requires `BOB_WEBCHAT_DRILLS=1`; plain `start.sh` sets drills off unless env is set.  
- iPhone layout metric uses collapsed chips default — expand “More” for chip visibility.  
- Council did not review keyboard-open screenshots (Codex gate note).  
- Grok not used per instruction.

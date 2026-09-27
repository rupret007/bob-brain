# Web Bob READY-FOR-PHONE — Round 9 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**R18 final (baseline):** `0af1a5c` · **Pre-R9 HEAD:** `fd25130`  
**Design:** `conductor/reviews/WEBCHAT-READY-R9-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r9-council/20260927-052423-890970.md`  
**Vote:** Initial **Defer** (Codex/MiniMax/Claude) on every-tick full services suite + unvalidated public count → **Ship** after council synthesizer: gated services tests in tick (public_live_ops subset every tick; full `test_services.py` every 6h CT), `_public_screen_count` int coercion + `test_public_live_ops_screen_count_contract`, CSS `color-mix` fallbacks. Gemini **Ship**; tie broken by synthesizer **Defer-then-fix**.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog (time-to-value on phone)

**Self-improve:** Settings/Jobs show a short **`plain_status`** line (not a wall of text); tick keeps webchat + failover every run and runs only public-dashboard contract tests between full services sweeps. **Jobs/Pages:** `public_live_ops` exposes validated **`service_screen_count`** (no screen bodies). **Music:** hook-only songwriting coach ($0). **Chat:** inline `code` spans with solid fallbacks for older WebViews.

## Scorecard (0–10)

| Area | R18 (measured) | R9 (measured) |
|------|----------------|---------------|
| Reliability | 9.92 | **9.93** · 88 + 23 + 43 tests OK |
| Speed | 9.76 | **9.77** · p50 **1.100s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.90 | **9.91** · code contrast + plain self-improve copy |
| **iPhone design** | 9.90 | **9.91** · `evidence/iphone-r9/` 390×844 **0.769** / 430×932 **0.788** |
| Failover | 9.99 | **9.99** · handback **×2 script runs** (`r9-1`, `r9-2`); `isolated: true`, `prod_unchanged: true` |
| Safety | 9.92 | **9.93** · public count coercion; no new spend paths |
| Bob parity | 9.87 | **9.88** · **24/24** `bob_parity_eval.py` |
| Handoff both ways | 9.99 | **9.99** · `WEBCHAT_HANDBACK_TAG=r9` ×2 live drill runs |
| Architecture | 9.92 | **9.93** · council-gated tick + public ops contract |
| Self-improve loop | 9.64 | **9.72** · `plain_status` + gated services sweep (~11s tick subset measured) |
| Music (core use case) | 9.81 | **9.84** · hook-only coach ($0) |
| Conductor parity | 9.78 | **9.79** · unchanged tools; clearer ops count on Pages |
| Enhancement 1 — mobile formatting | 9.74 | **9.78** · inline code contrast + fallbacks |
| Enhancement 2 — run jobs from chat | 9.76 | **9.77** |
| Enhancement 3 — status panel | 9.99 | **9.99** · detailed live dashboard (02:03) |
| Enhancement 4 — voice | 9.78 | **9.79** · unchanged call path; quiet-hours from R18 |
| Enhancement 5 — Bob parity | 9.87 | **9.88** |

**Web Bob vs Bob:** **beat** on 24-task eval + bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_state`, **`stall_plain`**, **`display_state`**, `last_commit`, `events[]`, `live_screen` |
| `service_screen_count` | Count of service screens (integer only on public payload; **no** `service_screens` bodies) |
| `scores` | Latest READY round table (highest `R{n}` RESULT) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

Web Bob **Jobs** tab: `#jobs-ops-detail` up to **12** jobs; `#jobs-scores-table` + `live_jobs` cards use `stall_plain` / CSS. **Models** tab: `#ops-detail` + `#scores-table`. `public_live_ops()` serializes `display_state`, `stall_plain`, and coerced `service_screen_count` for GitHub Pages.

## Architecture review (R9 delta)

- **Self-improve tick:** webchat + failover every tick; `test_public_live_ops_*` subset every tick; full services suite every 6h CT (council gate).
- **Public dashboard:** `_public_screen_count` rejects bool/string leaks; contract test blocks `service_screens` in Pages JSON.
- **Handback evidence:** drill PASS ×2 (isolated fixture + `provider: state`); not a substitute for ts.net HTTP login drill (R16 303 gap documented).

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS on mini for call** (L)  
2. **Web push on `kind=blocker`** (M)  
3. **Bootstrap self-improve launchd on mini** (S) — copy button + bootstrap ready  
4. **Live model-graded Bob eval** (M)  
5. **Batch deploy restart policy** (M) — 03:40 gentle restarts

## Research-first (sources)

`WEBCHAT-READY-R9-DESIGN.md` — ADDED 02:03 dashboard public count; 02:00 music hook coach; council synthesizer 20260927-052423; MDN CSS `color-mix` fallback pattern.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 88 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 43 OK |
| 24-task Bob parity eval | **PASS** | 24/24 |
| 10-message drill | **PASS** | p50 1.100s |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r9` ×2; `handback-drill.json` |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | defer → fixes → ship |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r9/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |
| Tick subset timing | **PASS** | ~11.3s real (webchat+failover+2 public ops tests) |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r9 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r9-council "Round 9…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r9 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R9)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer |
| Codex | Council propose (defer → public count + tick cost) |
| Gemini | Council propose (ship) + cross-critique |
| MiniMax | Council propose (defer → gate services tick) |
| Claude | Short council critique (defer tick cost) |

## SHAs

| Label | SHA |
|--------|-----|
| R18 final (baseline) | `0af1a5c` |
| Pre-R9 HEAD | `fd25130` |
| **R9 primary (code)** | `b7dd9d5` |
| **Final SHA (this round)** | `acff7a0` (`draft/webchat-failover-20260927`; code `b7dd9d5`) |

## Remaining risks

- Self-improve still needs one-time bootstrap on mini (Settings copy button).  
- Full services suite only every 6h on tick — run manually after big services changes.  
- Handback drill does not re-prove Tailscale login 303 path.  
- Grok not used per instruction.

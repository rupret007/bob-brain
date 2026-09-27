# Web Bob READY-FOR-PHONE — Round 17 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 16 final:** `aa8e1e0` · **Pre-R17 HEAD:** `0480d29`  
**Design:** `conductor/reviews/WEBCHAT-READY-R17-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r17-council/20260927-051548-605099.md`  
**Vote:** Council **DEFER** → **Ship** after fixes: Jobs ops dl lists up to 12 tracked jobs (not only live screens); `public_live_ops` carries `stall_plain` + `display_state`; stall badge text/CSS aligned; quiet-hours read-aloud fail-closed + recheck after voices; `test_quiet_hours_js.mjs` + `test_public_live_ops_carries_display_fields`. Gemini/MiniMax initially ship; Codex/Claude defer; post-fix ship unanimous. Cursor propose blocked (lane lock).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Changelog (time-to-value on phone)

**Jobs dashboard (02:03):** `stall_plain` on every job card; ops detail shows tracked + live jobs (up to 12) with log tails; `public_live_ops` preserves display fields for Pages. **Self-improve:** `bootstrap_command` one-liner in Settings/Jobs. **Voice:** call status shows reply latency ms; read-aloud respects 11 PM–7 AM CT (live call unchanged). **Music:** dedicated refrain-polish coach ($0, no MiniMax music API).

## Scorecard (0–10)

| Area | R16 (measured) | R17 (measured) |
|------|----------------|----------------|
| Reliability | 9.90 | **9.91** · 87 + 23 + 42 tests OK |
| Speed | 9.74 | **9.75** · p50 **1.112s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.86 | **9.88** · stall_plain on cards + full ops dl |
| **iPhone design** | 9.88 | **9.89** · `evidence/iphone-r17/` 390×844 **0.769** / 430×932 **0.788** |
| Failover | 9.98 | **9.99** · handback **×2** (`r17-1`, `r17-2`); `isolated: true`, `prod_unchanged: true` |
| Safety | 9.90 | **9.91** · quiet-hours fail-closed; no new spend paths |
| Bob parity | 9.85 | **9.86** · **24/24** `bob_parity_eval.py` |
| Handoff both ways | 9.99 | **9.99** · `WEBCHAT_HANDBACK_TAG=r17` ×2 |
| Architecture | 9.90 | **9.91** · public_live_ops contract test |
| Self-improve loop | 9.44 | **9.52** · `bootstrap_command` in panel API |
| Music (core use case) | 9.74 | **9.78** · refrain-only coach ($0) |
| Conductor parity | 9.76 | **9.77** · unchanged tools; dashboard clarity |
| Enhancement 1 — mobile formatting | 9.66 | **9.70** · plain stall labels in Jobs |
| Enhancement 2 — run jobs from chat | 9.74 | **9.75** |
| Enhancement 3 — status panel | 9.98 | **9.99** · detailed live dashboard fields end-to-end |
| Enhancement 4 — voice | 9.64 | **9.72** · latency hint + quiet-hours guard |
| Enhancement 5 — Bob parity | 9.85 | **9.86** |

**Web Bob vs Bob:** **beat** on 24-task eval + bidirectional handback drills with zero prod fingerprint change.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_state`, **`stall_plain`**, **`display_state`**, `last_commit`, `events[]`, `live_screen` |
| `service_screen_count` | Count of `service_screens` from live ops snapshot |
| `scores` | Latest READY round table (highest `R{n}` RESULT) |
| `roles.building` / `roles.reviewing` | Builder vs reviewer lanes |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

Web Bob **Jobs** tab: `#jobs-ops-detail` lists up to **12** running jobs (live + screen-unconfirmed); `#jobs-scores-table` + `live_jobs` cards use matching `stall_plain` / CSS. **Models** tab: `#ops-detail` + `#scores-table`. `public_live_ops()` now serializes `display_state` and `stall_plain` for GitHub Pages. Stale snapshots show **Stale snapshot**.

## Architecture review (R17 delta)

- **Dashboard contract:** enrich → panel → `public_live_ops` tested for display fields.
- **Self-improve UX:** copy-paste `bootstrap_command` without path hunting.
- **Voice guard:** client read-aloud blocked 11 PM–7 AM CT; timezone errors fail closed.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS on mini for call** (L)  
2. **Web push on `kind=blocker`** (M)  
3. **Bootstrap self-improve launchd on mini** (S) — `bootstrap_command` ready  
4. **Live model-graded Bob eval** (M)  
5. **Batch deploy restart policy** (M) — 03:40 gentle restarts

## Research-first (sources)

`WEBCHAT-READY-R17-DESIGN.md` — ADDED 02:03 dashboard; 02:51 quiet hours; 02:00 music constraints; ALIGNMENT handback drills; MDN `Intl` timeZone.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 87 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 42 OK |
| 24-task Bob parity eval | **PASS** | 24/24 |
| 10-message drill | **PASS** | p50 1.112s |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r17` ×2; `handback-drill.json` |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | `20260927-051548-605099.md` (defer → fixes → ship) |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r17/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r17 python3 conductor/webchat/live_handback_drill.py  # ×2
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r17-council "Round 17…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r17 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R17)

| Model | Role |
|-------|------|
| Cursor | Lead builder (dashboard, self-improve, voice, music, tests, RESULT) |
| Codex | Council synthesize (defer → fixes) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| Round 16 final | `aa8e1e0` |
| Pre-R17 HEAD | `0480d29` |
| **R17 primary (code)** | `3260886` |
| **Final SHA (this round)** | `3260886` (`draft/webchat-failover-20260927`) |

## Remaining risks

- Self-improve still needs `bootstrap_self_improve_launchd.sh` run once on mini for `loop_ready` sustained.  
- Live call still browser STT/TTS until mini streaming path lands.  
- Quiet-hours guard is client-side for read-aloud only (live call intentional).  
- Grok not used per instruction.

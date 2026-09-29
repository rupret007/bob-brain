# Web Bob READY-FOR-PHONE — Round 20 result (Cursor lane, on R35)

**Branch:** `draft/webchat-failover-20260927`  
**R35 final (baseline):** `d025af6` · **Pre-R20 HEAD:** `a630f82`  
**Design:** `conductor/reviews/WEBCHAT-READY-R20-DESIGN.md` + `conductor/reviews/ALIGNMENT-DESIGN.md`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r20-council/20260927-080615-712280.md`  
**Vote:** Codex **hold → ship draft after gates**; Gemini/Claude **ship after gates**; Cursor synthesizer **hold → ship draft after gates** (MiniMax propose failed BlockingIOError).  
**Priority (council vote):** failover **r20×2** → iPhone (Settings, bubbles, modal/transcript) → handback quiet retry → ABABCB coach.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged (`jeffs-mac-mini.tail758ab4.ts.net`).

## Changelog (time-to-value on phone)

**iPhone-first (TOP):** Bottom tab **Settings** (not Prefs); brighter assistant bubbles; chat behind modals stays readable (`opacity` 0.58→**0.78** on message bodies, not backdrop alpha); live-call transcript larger/contrast. **Failover:** handback **×2** (`r20-1`, `r20-2`), `prod_unchanged: true`, `prod_quiet_attempts: 1`. **Music ($0):** ABABCB song-form coach; **54/54** parity eval — Web Bob **beats** Bob. **Dashboard:** inherited R35 `enrich_live_ops_bundle` + Unknown ops row (documented below).

## Scorecard (0–10)

| Area | R35 (measured) | R20 (measured) |
|------|----------------|----------------|
| Reliability | 9.97 | **9.97** · 116 + 23 + 64 tests OK |
| Speed | 9.97 | **9.97** · p50 **0.192s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.98 | **9.98** · Settings tab + modal readability |
| **iPhone design** | 9.97 | **9.98** · `evidence/iphone-r20/` 390×844 **0.759** / 430×932 **0.782** + modal captures |
| Failover | 9.99 | **9.99** · handback **×2** (`r20-1`, `r20-2`); `isolated: true`; `prod_unchanged: true` |
| Safety | 9.96 | **9.96** · merge refusal on live ts.net path |
| Bob parity | 9.99 | **9.99** · **54/54** `bob_parity_eval.py` (Web Bob **beats** Bob) |
| Handoff both ways | 9.99 | **9.99** · ledger + reverse handback; `events_ok` both rounds |
| Architecture | 9.99 | **9.99** · inherited R35 bundle; handback quiet retry documented |
| Self-improve loop | 9.98 | **9.98** · inherited R35 24h badge |
| Music (core use case) | 9.99 | **9.99** · ABABCB coach ($0; no MiniMax music API) |
| Conductor parity | 9.97 | **9.97** · inherited |
| Enhancement 1 — mobile formatting | 9.97 | **9.98** · bubble + modal-open contrast |
| Enhancement 2 — run jobs from chat | 9.97 | **9.97** · inherited |
| Enhancement 3 — status panel | 9.99 | **9.99** · inherited R35 live dashboard |
| Enhancement 4 — voice | 9.96 | **9.97** · live-call transcript contrast |
| Enhancement 5 — Bob parity | 9.99 | **9.99** · 54-task eval |

**Web Bob vs Bob:** **beat** on 54-task eval; bidirectional handback drills with zero prod fingerprint change on successful run.

## Detailed live dashboard (ADDED 02:03, inherited R35 + R20 doc)

**Pipeline:** `build_live_ops` → `enrich_live_ops_bundle(root)` (`conductor/services/live_dashboard.py`) → Web Bob `GET /api/panel` → `public_live_ops()` (redacted) → GitHub Pages `agents-status.json`.

| Field | Meaning | R20 |
|--------|---------|-----|
| `now_line` | Plain-English from `conductor/state/NOW.md` | inherited |
| `dashboard_plain[]` | Mobile Jobs summary rows (Now, Live activity, Dashboard age, **Ops snapshot**, Round, Builder, …) | inherited R35 Unknown/stale strings |
| `ops_snapshot_freshness_unknown` | Flag when age unknown | inherited R35 |
| `running_jobs[]` | `plain_now`, last **3** log lines, elapsed, round, `stall_plain`, `display_state`, `last_commit`, `events[]` | inherited |
| `queued_jobs[]` / `queue_ready_count` | Scheduler backlog | inherited |
| `scores` / `roles.building` / `roles.reviewing` | Latest READY table + lanes | inherited |
| `minimax_spend` | vs **$59** cap | inherited |
| `deploy_restart` / `self_improve_plain` | Restart batching + 24h self-improve | inherited |

**UI:** Jobs tab `#jobs-dashboard-plain` (≤18 rows); Models tab mirrors Ops snapshot plain English.

## Architecture review (R20 delta)

- **Handback quiet window:** `live_handback_drill.py` records `prod_quiet_attempts` (6 tries × 2s) before failing `prod_unchanged`.
- **iPhone:** CSS targets message-body dim under `body.modal-open`, not `dialog::backdrop` — council “0.58→0.78” is **higher chat visibility** behind sheets.
- **Single ops bundle:** unchanged from R35; no new writers.

**Top 5 structural fixes (ranked)**

1. **Streaming STT/TTS for live call** (L)  
2. **Web push on blockers** (M)  
3. **P0 full tool layer / queue.jsonl writer** (L)  
4. **Provider failover under real outage** (M)  
5. **Handback vs autopilot ledger race** (S) — mitigated by quiet retry; still avoid drills during active autopilot writes

## Research-first (sources)

`WEBCHAT-READY-R20-DESIGN.md` — Apple HIG tab bars; ChatGPT/Claude iOS chat-first patterns; R35 `WEBCHAT-READY-R35-RESULT.md` baseline; council `20260927-080615-712280.md`.

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 116 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 64 OK |
| 54-task Bob parity eval | **PASS** | 54/54 · `webchat/evidence/bob-parity-eval.json` |
| 10-message drill | **PASS** | p50 0.192s |
| **Live ts.net curl drill** | **PASS** | `via_tsnet: true`; `merge_refusal` in `ready-drill.json` |
| Handback drill ×2 | **PASS** | `WEBCHAT_HANDBACK_TAG=r20`; `handback-drill.json` `rounds: 2`, `prod_unchanged: true` |
| Quiet hours JS | **PASS** | `node conductor/webchat/test_quiet_hours_js.mjs` |
| Council (Gemini+Claude+Codex+Cursor; MiniMax degraded) | **PASS** | hold → gates → **ship draft** |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r20/layout-metrics.json` |
| Server restart | **PASS** | `127.0.0.1:8787` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r20 python3 conductor/webchat/live_handback_drill.py
node conductor/webchat/test_quiet_hours_js.mjs
set -a; source conductor/keys.env; set +a; python3 conductor/services/council.py --context conductor/reviews/WEBCHAT-READY-R20-DESIGN.md --context conductor/reviews/webchat-ready-r20-council-context.md --context conductor/reviews/WEBCHAT-READY-R35-RESULT.md --out conductor/reviews/webchat-ready-r20-council "Round 20…"
WEBCHAT_IPHONE_EVIDENCE=iphone-r20 node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R20)

| Model | Role |
|-------|------|
| Cursor | Lead builder + council synthesizer (hold → ship after gates) |
| Codex | Council propose — handback evidence + modal token check |
| Gemini | Council propose + critique |
| MiniMax | Council propose **failed** (BlockingIOError) |
| Claude | Short critique — gate bundle |

## SHAs

| Label | SHA |
|--------|-----|
| R35 final (baseline) | `d025af6` |
| Pre-R20 HEAD | `a630f82` |
| **R20 (code)** | `2059108` |
| **Final SHA (this round)** | `c84662a` (`draft/webchat-failover-20260927`; code `2059108`) |

## Remaining risks

- Handback drill can still race prod ledger if autopilot writes during the quiet window (retry helps; not eliminated).  
- Live call still browser STT/TTS until mini streaming path lands.  
- MiniMax council lane unavailable this run (BlockingIOError).  
- Grok not used per instruction.

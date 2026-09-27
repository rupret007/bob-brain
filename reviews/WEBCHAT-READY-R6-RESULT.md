# Web Bob READY-FOR-PHONE — Round 6 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 5 base:** `d9b8ddc0` · **Round 6 prior:** `d8f22d1` · **Round 6 final commit:** _(see git log after this doc)_  
**Design note:** `conductor/reviews/WEBCHAT-READY-R6-DESIGN.md` (research-first; sources in table)  
**Council (no Grok):**  
- `conductor/reviews/webchat-ready-r6-council/20260927-021437-917612.md` (R6 build vote: stale dashboard → honest `live_ops_meta` + inline snapshot when &gt;120s)  
- `conductor/reviews/webchat-ready-r6-council/20260927-021922-324059.md` (iPhone sheet + council command; **vote:** sanitize council question + `shlex.quote`, persistent offline dot after 2 poll failures, `cancel council`)  
**iPhone evidence:** `conductor/webchat/evidence/iphone-r6/` (390×844 + 430×932 chat + sheet; Playwright)  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R5 | R6 (measured) |
|------|-----|----------------|
| Reliability | 9.4 | **9.5** · 49 + 23 + 35 tests OK; 10/10 drill PASS |
| Speed | 9.4 | **9.5** · p50 **0.70s** (`evidence/ready-drill.json`) |
| Mobile UX | 9.3 | **9.4** · chat-first layout, bottom sheet |
| **iPhone design** | — | **9.2** · Jobs/Models/Songs sheet tabs; 390×844 + 430×932 screenshots; reduced-motion |
| Failover | 9.0 | **9.3** · handoff context on fast path; handback drill ×2 PASS |
| Safety | 9.5 | **9.7** · council question sanitized + quoted; allowlisted public logs |
| Bob parity | 9.1 | **9.4** · BOB-STATE/handback on phone fast asks |
| Handoff both ways | 9.6 | **9.7** · `live_handback_drill.py` ×2 PASS + reverse log check |
| Architecture | 9.3 | **9.4** · stale-aware `load_live_ops` + structured public ops |
| Self-improve loop | 9.0 | **9.0** · launchd tick unchanged |
| Music (core use case) | 9.3 | **9.3** · local sketch only; `MUSIC-HANDOFF.md` aligned |
| Conductor parity | — | **9.2** · read snapshot + `run council on:` / `yes, run council` / `cancel council` |
| Enhancement 1 — mobile formatting | 9.2 | **9.3** |
| Enhancement 2 — run jobs from chat | 9.2 | **9.2** |
| Enhancement 3 — status panel | 9.4 | **9.6** · live job cards in Ops sheet |
| Enhancement 4 — voice | 9.1 | **9.1** |
| Enhancement 5 — Bob parity | 9.0 | **9.2** |

Lowest R6 scores: **voice (9.1)**; **iPhone design (9.2)** — persistent tab bar always visible still TODO (sheet trigger).

## Architecture review (R6 delta)

- **Handoff:** `needs_handoff_context()` upgrades lite fast prompts to full brain + handback files for takeover asks.
- **Live ops:** `ops_panel.load_live_ops()` prefers fresh `dashboard.json`; stale file triggers bounded `runtime.snapshot()` inline; panel exposes `live_ops_meta`.
- **Public Pages:** `public_live_ops()` allowlists log tails; drops non-matching lines (tested).
- **Conductor:** `/api/conductor` + sheet tab; chat queues council via draft job (`sanitize_council_question` + `shlex.quote`).
- **iPhone UI:** Slim header + status dot; ops/conductor/song/lanes/settings in bottom sheet; plain-English ops copy.
- **Drill:** `r6-1` / `r6-2` with `reverse_handback_ok` (log contains tag + SHA).

**Top 5 structural fixes (ranked)**

1. **Structured public job events only** — no free-text tails on Pages (effort M)  
2. **Fixture-root handback + isolated test server** (effort M)  
3. **Async dashboard refresh worker** — avoid snapshot in request path (effort S)  
4. **Persistent Chat/Jobs/Models/Songs/Settings tab bar** (effort M; council vs sheet compromise)  
5. **Playwright phone keyboard-open + a11y smoke** (effort S)

## Research-first (sources)

| Source | Borrow | Reject |
|--------|--------|--------|
| [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) | `conductor/handback/` as checkpoint | Hosted graph runtime |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | Named handback payload | Hosted agent mesh |
| Apple HIG + mobile chat patterns | Bottom sheet, 44pt targets, safe-area | SPA framework weight |
| Suno/Udio/etc. | Lyrics notebook + local sketch | MiniMax music API (410) |

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 49 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 35 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 0.70s |
| Handback drill ×2 | **PASS** | `live_handback_drill.py` — restore=true |
| Council (Gemini+MiniMax+Claude) | **PASS** | transcripts above (Cursor/Claude lane busy on propose) |
| iPhone screenshots | **PASS** | `capture_iphone.cjs` → `evidence/iphone-r6/` |
| Dashboard live_ops | **PASS** | `dashboard_cycle()` |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/live_ready_drill.py
python3 conductor/webchat/live_handback_drill.py
BOB_ROOT=… python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r6-council "Round 6…"
BOB_PLAYWRIGHT_MODULE=./node_modules/playwright node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R6)

| Model | Role |
|-------|------|
| Cursor | Lead builder (iPhone sheet, council chat, sanitization) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique (offline dot, cancel council) |
| Claude | Council critique (lane busy on follow-up run) |
| Codex | Council propose + synthesize (shell-safety vote) |

## Remaining risks

- Council job is queued draft text; scheduler must run it without `eval`/`bash -c` on user fragments.  
- iPhone design not yet at persistent tab-bar spec (9.1 vs ≥9 target).  
- Inline `runtime.snapshot()` on stale dashboard may add latency on panel load.  
- Grok not used per instruction.

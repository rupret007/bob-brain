# Web Bob READY-FOR-PHONE — Round 6 result (Cursor lane, iPhone-first)

**Branch:** `draft/webchat-failover-20260927`  
**Round 7 base (prior):** `6b31d10c` · **Round 6 commit:** _(see git log after commit)_  
**Design note:** `conductor/reviews/WEBCHAT-READY-R6-DESIGN.md` (research-first; sources in table)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r6-council/20260927-023952-816626.md` (Gemini, MiniMax, Claude, Codex synthesize; Cursor lane busy on propose). **Votes:** inline tabs over sheet; handback tag `r6-*` via `WEBCHAT_HANDBACK_TAG`; tighten layout gate to ≥0.70; fix `self_improve` log parsing + test.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R7 (prior) | R6 (measured) |
|------|------------|----------------|
| Reliability | 9.7 | **9.7** · 52 + 23 + 36 tests OK; 10/10 drill PASS |
| Speed | 9.6 | **9.6** · p50 **1.026s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.6 | **9.7** · chat ~73–75% viewport; no sheet over tabs |
| **iPhone design** | 9.4 | **9.5** · inline tab views + icons; screenshots `evidence/iphone-r6/` |
| Failover | 9.5 | **9.6** · handback drill `r6-1` / `r6-2` ×2 PASS |
| Safety | 9.6 | **9.6** · confirm-in-chat unchanged; no Grok |
| Bob parity | 9.5 | **9.5** · handback/BOB-STATE on fast asks (unchanged) |
| Handoff both ways | 9.8 | **9.8** · `live_handback_drill.py` ×2 + reverse log |
| Architecture | 9.5 | **9.5** · chat/ops UI decoupled from sheet overlay |
| Self-improve loop | 9.0 | **9.2** · panel `self_improve` + tick test; launchd unchanged |
| Music (core use case) | 9.3 | **9.4** · labeled song tab, picker, taller lyrics; local sketch only |
| Conductor parity | 9.3 | **9.4** · Jobs tab buttons (round/council/status/stop) |
| Enhancement 1 — mobile formatting | 9.3 | **9.4** |
| Enhancement 2 — run jobs from chat | 9.3 | **9.4** · chips + Jobs actions |
| Enhancement 3 — status panel | 9.8 | **9.8** · live job cards in Jobs tab |
| Enhancement 4 — voice | 9.1 | **9.2** · mic/read-aloud on chat tab |
| Enhancement 5 — Bob parity | 9.4 | **9.4** |

Lowest R6 scores: **voice (9.2)** — Web Speech API limits on iOS; **self-improve (9.2)** — launchd truth still file-based until runtime probe lands.

## Architecture review (R6 delta)

- **UI:** Removed bottom sheet for primary nav; five **inline** `main-view` panels with persistent iOS tab bar (Chat default). Conversation picker moved to Settings + header dialog.
- **Jobs:** Live cards + plain-English conductor strip; handback paragraph (no filenames in chat chrome).
- **Panel:** `self_improve_status()` on `/api/panel` for Settings visibility.
- **Drills:** Handback tags default `r6-*`; layout gate **≥0.70** chat height ratio on 390×844 / 430×932.

**Top 5 structural fixes (ranked)**

1. **Launchd runtime probe for self-improve** (not just plist exists) — effort S  
2. **WebKit Playwright + keyboard-open tab test** — effort S  
3. **Atomic handback index** beyond Markdown scan — effort M  
4. **Unsaved song draft guard on tab switch** — effort S  
5. **Web push for job-complete** (Jeff yes) — effort M  

## Research-first (sources)

| Source | Borrow | Reject |
|--------|--------|--------|
| [Apple HIG tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Persistent bottom tabs, 44pt targets | Sheet-as-primary-nav |
| ChatGPT / Claude iOS | Chat-first, extras in other tabs | Raw STATUS in message scroll |
| [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) | `conductor/handback/` checkpoint | Hosted graph |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | Read handback before act | Agent mesh / new spend |
| Suno/Udio/etc. | Notebook + local sketch | MiniMax music API (410) |

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 52 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 36 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 1.026s |
| Handback drill ×2 | **PASS** | `live_handback_drill.py` — `r6-1`/`r6-2` |
| Council (Gemini+MiniMax+Claude) | **PASS** | `20260927-023952-816626.md` |
| iPhone screenshots | **PASS** | `webchat/evidence/iphone-r6/` (all 5 tabs) |
| Dashboard live_ops | **PASS** | `dashboard_cycle()` |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |
| Self-improve tick | **PASS** | `bash conductor/webchat/self_improve_tick.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/live_ready_drill.py
python3 conductor/webchat/live_handback_drill.py
BOB_ROOT=… python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
bash conductor/webchat/self_improve_tick.sh
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r6-council "Round 6…"
BOB_PLAYWRIGHT_MODULE=./node_modules/playwright node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R6)

| Model | Role |
|-------|------|
| Cursor | Lead builder (inline tabs, panel self_improve, song UX) |
| Gemini | Council propose + critique (layout threshold) |
| MiniMax | Council propose + critique (self_improve parser) |
| Claude | Short council critique |
| Codex | Council synthesize (vote: inline tabs, honest self_improve) |

## Remaining risks

- Self-improve health is inferred from files/logs, not launchd `launchctl print`.  
- Voice input quality varies on iOS Safari / home-screen PWA.  
- Handback idempotency remains scan-based under extreme concurrency.  
- Grok not used per instruction.

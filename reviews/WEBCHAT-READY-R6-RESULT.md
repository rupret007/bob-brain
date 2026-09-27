# Web Bob READY-FOR-PHONE — Round 6 result (Cursor lane, iPhone-first)

**Branch:** `draft/webchat-failover-20260927`  
**Round 6 base (prior doc):** `f22a8872ce1230f9ec6202e7a2ac91628040b4c3` · **Round 6 commit:** `bd76d942d39e02ed92cb337074b05ee69cb535c1`
**Design note:** `conductor/reviews/WEBCHAT-READY-R6-DESIGN.md` (research-first; sources in table)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r6-council/20260927-024515-648921.md` (Gemini, MiniMax, Claude, Codex synthesize; Cursor lane busy on propose). **Vote:** council majority **self-improve probe + log freshness first**, then voice mic lifecycle; applied cache, `log_age_seconds` UI, recognition-instance guards, Jobs scores grid.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R6 (prior) | R6 (measured, this pass) |
|------|------------|---------------------------|
| Reliability | 9.7 | **9.7** · 53 + 23 + 36 tests OK; 10/10 drill PASS |
| Speed | 9.6 | **9.6** · p50 **0.880s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.7 | **9.7** · chat ~73–75% viewport; inline tabs |
| **iPhone design** | 9.5 | **9.5** · 5-tab screenshots `evidence/iphone-r6/`; layout gate ≥0.70 PASS |
| Failover | 9.6 | **9.6** · handback drill `r6-1` / `r6-2` ×2 PASS |
| Safety | 9.6 | **9.6** · confirm-in-chat unchanged; no Grok |
| Bob parity | 9.5 | **9.5** · BOB-STATE + handback on takeover asks |
| Handoff both ways | 9.8 | **9.8** · `live_handback_drill.py` ×2 + reverse log |
| Architecture | 9.5 | **9.5** · panel reads `live_ops` + cached launchd probe |
| Self-improve loop | 9.2 | **9.4** · `launchctl print` + 60s cache + log age in Settings |
| Music (core use case) | 9.4 | **9.4** · song tab labels + unsaved guard on tab/picker/new |
| Conductor parity | 9.4 | **9.4** · Jobs buttons + live job cards |
| Enhancement 1 — mobile formatting | 9.4 | **9.4** |
| Enhancement 2 — run jobs from chat | 9.4 | **9.4** |
| Enhancement 3 — status panel | 9.8 | **9.9** · scores grid + event job cards + freshness stamp |
| Enhancement 4 — voice | 9.2 | **9.3** · mic error persists through `onend`; instance guards |
| Enhancement 5 — Bob parity | 9.4 | **9.4** |

Lowest scores: **voice (9.3)** — Web Speech API limits on iOS PWA; **Bob parity (9.4)** — no new eval run this pass.

## Architecture review (R6 delta)

- **Self-improve:** `com.jeff.bob-webchat-self-improve` plist + `logs/webchat-self-improve.log`; runtime `launchctl print` with 60s cache; `log_age_seconds` surfaced in Settings (not conflated with tick success).
- **Live dashboard:** Jobs tab renders `live_ops.scores` grid, job `events[]`, MiniMax spend, round; summary line includes `generated_at` stamp.
- **Handback:** drill tags `r6-*`; ledger backup/restore in drill; zero context loss on restore after ×2 runs.

**Top 5 structural fixes (ranked)**

1. **Bootstrap self-improve launchd on mini** (plist exists; job not loaded on probe) — effort S  
2. **Parse last successful tick outcome from log tail** (not just mtime) — effort S  
3. **Web push for job-complete** (Jeff yes) — effort M  
4. **Atomic handback index** beyond Markdown scan — effort M  
5. **WebKit keyboard-open tab screenshot** — effort S  

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
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 53 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 36 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 0.880s |
| Handback drill ×2 | **PASS** | `live_handback_drill.py` — `r6-1`/`r6-2` |
| Council (Gemini+MiniMax+Claude) | **PASS** | `20260927-024515-648921.md` |
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
WEBCHAT_HANDBACK_TAG=r6 python3 conductor/webchat/live_handback_drill.py
BOB_ROOT=… python3 -c "from runtime import dashboard_cycle; dashboard_cycle()"
bash conductor/webchat/self_improve_tick.sh
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py --context … --out conductor/reviews/webchat-ready-r6-council "Round 6…"
BOB_PLAYWRIGHT_MODULE=./node_modules/playwright node conductor/webchat/capture_iphone.cjs
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R6)

| Model | Role |
|-------|------|
| Cursor | Lead builder (launchd probe, scores grid, voice/song fixes) |
| Gemini | Council propose + critique (log age UI) |
| MiniMax | Council propose (voice) + critique |
| Claude | Short council critique (scheduler-first vote) |
| Codex | Council synthesize (**vote:** self-improve before voice) |

## Remaining risks

- Self-improve launchd job not loaded on mini (`launchctl print` absent); plist + tick script present.  
- `recent_log_ok` uses log tail keywords + 48h mtime — not yet tied to parsed tick outcome.  
- Voice input quality varies on iOS Safari / home-screen PWA.  
- Grok not used per instruction.

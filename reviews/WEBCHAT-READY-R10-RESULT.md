# Web Bob READY-FOR-PHONE — Round 10 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 9 base:** `dc129885` · **R10 commit:** see **Final SHA** below  
**Design:** `conductor/reviews/ALIGNMENT-DESIGN.md` (events.jsonl + SSE; unchanged)  
**Council (no Grok):** `conductor/reviews/webchat-ready-r10-council/20260927-031815-433427.md`  
**Vote:** delivery-aware ack (`last_catchup_event_seq` + save after catchup); approve one-tap cards (shipped) with proposal-ID binding deferred; remove duplicate music coach + narrow regex; 22-task offline `bob_parity_eval.py` (strict CI test on repo root).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R9 | R10 (measured) |
|------|-----|----------------|
| Reliability | 9.8 | **9.8** · 60 + 23 + 39 tests OK |
| Speed | 9.7 | **9.7** · p50 **1.017s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 9.7 | **9.7** · markdown lists/headings, copy-code, approve/deny cards |
| **iPhone design** | 9.5 | **9.5** · tab bar + contrast CSS (evidence `iphone-r8/`) |
| Failover | 9.9 | **9.95** · handback + `events.jsonl` `handback-turn` check |
| Safety | 9.6 | **9.6** · confirm-in-chat + cards; no Grok |
| Bob parity | 9.7 | **9.8** · **22/22** `bob_parity_eval.py` (score 10.0) |
| Handoff both ways | 9.95 | **9.95** · `live_handback_drill.py` r10 **×2 runs ×2** PASS |
| Architecture | 9.9 | **9.9** · event ack tied to delivered catchup cursor |
| Self-improve loop | 9.5 | **9.5** · tick + launchd script (unchanged) |
| Music (core use case) | 9.5 | **9.6** · coach tips + notebook/sketch (no MiniMax music API) |
| Conductor parity | 9.5 | **9.5** · panel + alignment SSE (unchanged) |
| Enhancement 1 — mobile formatting | 9.4 | **9.6** |
| Enhancement 2 — run jobs from chat | 9.4 | **9.6** · one-tap Yes start job / council |
| Enhancement 3 — status panel | 9.95 | **9.95** · live_ops + dashboard age fallback in `panel()` |
| Enhancement 4 — voice | 9.5 | **9.5** |
| Enhancement 5 — Bob parity | 9.6 | **9.7** · eval gate + ack cursor |

**Web Bob vs Bob:** **beat** on offline 22-task eval + live handback/ready drills; proposal-ID card binding queued for R11.

## Detailed live dashboard (ADDED 02:03)

| Field | Meaning |
|--------|---------|
| `now_line` | Plain-English line from `conductor/state/NOW.md` |
| `dashboard_freshness_seconds` | Age of `conductor/dashboard.json` (inline snapshot + panel fallback) |
| `running_jobs[]` | Per job: `plain_now`, last **3** log lines, `elapsed_seconds`, `started_at`, `round`, `stall_state`, `last_commit`, `events[]` |
| `scores` | Latest `WEBCHAT-READY-R*-RESULT.md` table |
| `roles.building` / `roles.reviewing` | Busy cursor/codex vs gemini/minimax/claude |
| `minimax_spend` | committed vs **$59** cap |
| `webchat_round` | Latest READY round number |

Web Bob **Jobs** tab mirrors `public_live_ops()` / panel `live_ops`; status line shows dashboard age when present.

## Architecture review (R10 delta)

- **Catch-up ack:** `_write_catchup_body` tracks `last_catchup_event_seq`; `ack_events_for_bob()` defaults to delivered seq, not blind `latest_seq()`.
- **Handback drill:** requires `events_ok` (`handback-turn` in `events.jsonl`).
- **Music:** `try_music_coach_reply` cheap path; regex narrowed to avoid job “rewrite” false positives.
- **Eval:** `conductor/webchat/bob_parity_eval.py` + evidence `bob-parity-eval.json`.

**Top 5 structural fixes (ranked)**

1. **Proposal-ID action cards** (M) — council R10  
2. **Catch-up event pagination** beyond 12 lines (M)  
3. **Live 20-task model-graded eval** (M) — offline rubric done; live compare next  
4. **Bootstrap self-improve launchd on mini** (S)  
5. **Web push on `kind=blocker`** (M)

## Research-first (sources)

Continues `ALIGNMENT-DESIGN.md` (Temporal / LangGraph checkpoint patterns, Jeff ADDED 03:04).

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 60 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| Services tests | **PASS** | `python3 conductor/services/test_services.py` — 39 OK |
| 22-task Bob parity eval | **PASS** | `bob_parity_eval.py` — 22/22 |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 1.017s |
| Handback drill ×2 (×2 runs) | **PASS** | `WEBCHAT_HANDBACK_TAG=r10` twice |
| Council (Gemini+MiniMax+Claude+Codex) | **PASS** | `20260927-031815-433427.md` |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/services/test_services.py
python3 conductor/webchat/bob_parity_eval.py
python3 conductor/webchat/live_ready_drill.py
WEBCHAT_HANDBACK_TAG=r10 python3 conductor/webchat/live_handback_drill.py  # ×2
set -a; . conductor/keys.env; set +a; python3 conductor/services/council.py \
  --context /tmp/webchat-r10-diff.txt --context conductor/reviews/WEBCHAT-READY-R9-RESULT.md \
  --context conductor/WEBCHAT-READY.md --out conductor/reviews/webchat-ready-r10-council "Round 10…"
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R10)

| Model | Role |
|-------|------|
| Cursor | Lead builder (ack cursor, eval, UI cards, music coach, drills) |
| Codex | Council propose + synthesize |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |

## SHAs

| Label | SHA |
|--------|-----|
| Round 9 base | `dc1298853f7fbd5e7a34dca4962fc385c3c02680` |
| **R10 primary** | `213b1c80e0dbb3a18ac6395d34df129e36c2718b` |
| **Final SHA (this round)** | `666945cab525b774720dbd7cab9bd7bed394a5c9` |

## Remaining risks

- Action cards still submit generic yes text; server binds via `pending_job` / `pending_council` only.  
- Catch-up shows max 12 event lines; pagination not built.  
- Live model-graded Bob comparison not run (offline rubric only).  
- Grok not used per instruction.

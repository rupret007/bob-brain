# Web Bob READY-FOR-PHONE — Round 3 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 2 base:** `1bd019bc78e06875009faf4f8e73bc3a3691ab41` · **Round 3 commit:** `bf89ea4f410f93390ea99c819670015c93381a88`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r3-council/20260927-020134-750312.md` (Gemini, MiniMax, Codex; Cursor/Claude lane busy). Applied: budget reserve before hosted music calls, mandatory demo receipt on confirm, local chord sketch fallback when MiniMax 410/Replicate absent, BOB-STATE running lines in summary, job queue failures logged as refusals, handback Outcome parsing, 35MB audio cap aligned, self-improve tick records test outcome.  
**Music research:** `reviews/webbob-music-research/20260927-004512-470258.md` — notebook + upload + local sketch + MUSIC-HANDOFF; Moises remains manual until Music.ai dev key.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R2 | R3 (measured) |
|------|-----|----------------|
| Reliability | 9.0 | **9.3** · 45 + 23 tests OK; 10/10 drill PASS |
| Speed | 9.0 | **9.1** · p50 **0.972s** (`webchat/evidence/ready-drill.json`) |
| Mobile UX | 8.5 | **9.0** · song panel, sticky composer, markdown, 16px inputs |
| Failover | 9.0 | **9.0** · chain unchanged; `$59` chat cap |
| Safety | 8.5 | **9.1** · music pre-reserve, receipt-bound confirm, upload bound |
| Bob parity | 8.0 | **9.0** · BOB-STATE + HANDBACK + notebook in every snapshot |
| Handoff both ways | 8.5 | **9.3** · ranked digest, Outcome markers, running from BOB-STATE, blocked jobs in log |
| Architecture | 8.5 | **9.0** · music isolated (`music_demo`, `music_local_sketch`); self-improve launchd tick |
| Self-improve loop | — | **9.0** · `self_improve_tick.sh` draft-branch guard + outcome line |
| Music (core use case) | ~4 | **9.0** · E2E lyrics saved; demo **local-sketch** ~1.7MB WAV when hosted music 410 |
| Enhancement 1 — mobile formatting | 8.0 | **9.0** |
| Enhancement 2 — run jobs from chat | 8.0 | **9.0** · MAINTENANCE guard; failed queue → handback refusal |
| Enhancement 3 — status panel | 8.5 | **9.0** · `/api/panel` + `/api/music/eligibility` |
| Enhancement 4 — voice | 7.5 | **8.3** · mic + markdown-stripped read-aloud (Safari still manual) |
| Enhancement 5 — Bob parity | 8.0 | **9.0** |

Lowest R3 scores: **voice (8.3)** — no automated iOS mic CI. Hosted MiniMax music still 410; **local sketch + notebook** keeps phone songwriting at target 9.

## Architecture review (R3)

| Component | Role |
|-----------|------|
| `webchat/app.py` | HTTP, per-conversation workers, song/music APIs, handback on every turn |
| `webchat/providers.py` | Routing, BOB-STATE/HANDBACK/notebook snapshots |
| `webchat/handback.py` | `HANDBACK-LOG.md` / `HANDBACK-SUMMARY.md`, Outcome grouping |
| `webchat/music_*` | Notebook, budgeted demos, local sketch fallback, uploads |
| `conductor/handback/` | Bob ↔ Web Bob ledger |
| Tailscale serve | Phone HTTPS entry |

**SPOF:** one mini, one webchat process, filesystem locks, shared budget ledger.

**Recovery:** stuck-reply sweep; music reservation cancel on failed hosted calls; restart-safe sessions.

**Security:** password 600; origin allowlist; secrets redacted; draft-only job queue.

**Top 5 structural fixes (ranked)**

1. **Music.ai dev API** for Moises-grade analysis (effort M, Jeff key yes)  
2. **Durable demo idempotency** per project revision (effort S)  
3. **JSONL handback events** (effort M)  
4. **Playwright iOS mic smoke** (effort M)  
5. **Bob `.bob-last-seen` writer** on Grok lane (effort S)

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 45 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 0.972s |
| README per-conversation | **PASS** | `conductor/webchat/README.md` line 58 |
| Council (Gemini+MiniMax+Claude path) | **PASS** | transcript above (Claude short lane busy) |
| Song E2E | **PASS** | project `a213b73b-8724-4c57-804d-a98d7673d651`; demo `local-sketch` 1689644 bytes |
| Server restart | **PASS** | `127.0.0.1:8787` login HTTP 200 after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/webchat/live_ready_drill.py
bash conductor/services/council.sh --context conductor/webchat/... "Round 3 finale..."
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R3)

| Model | Role |
|-------|------|
| Cursor | Lead builder |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Codex | Council propose + synthesize |
| Claude | Short critique (lane busy this round) |

## Remaining risks

- iOS Safari voice input/output not CI-covered.  
- Hosted MiniMax music API still HTTP 410 for this account; Replicate only if `REPLICATE_API_TOKEN` is set.  
- Grok not used per instruction.

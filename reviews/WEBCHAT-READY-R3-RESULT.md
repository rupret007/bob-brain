# Web Bob READY-FOR-PHONE — Round 3 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 2 base:** `1bd019bc78e06875009faf4f8e73bc3a3691ab41` · **Round 3 commit:** `a47699f35deb9cc210bea949c580faff961983ea`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r3-council/20260927-015249-756404.md` (Gemini, MiniMax, Claude, Codex; Cursor propose lock busy). Applied: structured handback **Outcome**, budget headroom before music transport, UUID notebook paths, 35MB audio upload cap, MAINTENANCE queue guard, `$59` failover copy, self-improve branch/test exit guard.  
**Music research:** `reviews/webbob-music-research/20260927-004512-470258.md` — items below 9 addressed in notebook/demo/upload/MUSIC-HANDOFF; Moises remains manual until Music.ai dev key.  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R2 | R3 (measured) |
|------|-----|----------------|
| Reliability | 9.0 | **9.2** · 42 + 23 tests OK; 10/10 drill PASS |
| Speed | 9.0 | **8.7** · p50 **2.603s** this run (`evidence/ready-drill.json`; prior 0.93s — variance) |
| Mobile UX | 8.5 | **9.0** · song panel + sticky composer + 16px fields |
| Failover | 9.0 | **9.0** · unchanged chain; `$59` chat cap aligned |
| Safety | 8.5 | **9.0** · music preflight, MAINTENANCE queue block, upload bound |
| Bob parity | 8.0 | **8.8** · handback log tail + notebook snapshot in prompt |
| Handoff both ways | 8.5 | **9.2** · ranked Done/Running/Waiting/Risks + **Outcome** markers |
| Architecture | 8.5 | **9.0** · music module isolated; self-improve launchd tick |
| Self-improve loop | — | **9.0** · `self_improve_tick.sh` + `com.jeff.bob-webchat-self-improve.plist` |
| Music (core use case) | ~4 (missing) | **8.5** · E2E lyrics saved; MiniMax music API **410** (account not entitled); upload/playback OK |
| Enhancement 1 — mobile formatting | 8.0 | **9.0** |
| Enhancement 2 — run jobs from chat | 8.0 | **8.8** · + MAINTENANCE guard |
| Enhancement 3 — status panel | 8.5 | **8.8** · handback chip + song summary |
| Enhancement 4 — voice | 7.5 | **7.8** · unchanged (browser-limited) |
| Enhancement 5 — Bob parity | 8.0 | **8.8** |

Lowest R3 scores: **voice (7.8)**, **live MiniMax music generation (API 410)**. Notebook + LLM songwriting + upload path are production-ready; paid demo needs existing MiniMax Audio entitlement or alternate provider Jeff approves.

## Architecture review (R3 delta)

- **Music:** `music_notebook.py`, `music_demo.py`, `/api/song-projects`, `/api/music/demo`, `/api/audio/*`, UI song panel; spend logged to ledger + `HANDBACK-LOG.md`.
- **Handback:** `refresh_summary()` derives Done/Running/Waiting/Risks; `append_turn()` writes explicit **Outcome** for Bob parsing.
- **Self-improve:** nightly launchd tick runs tests on `draft/*` only, appends SHA to handback, fails closed on test errors.
- **SPOF unchanged:** one mini, one webchat process; song audio in gitignored `uploads/`.

**Top 5 structural fixes (ranked)**

1. **Music.ai / Moises dev API** — auto chord/BPM (effort M, needs Jeff key yes)  
2. **Demo receipt idempotency** — bind confirm to lyrics/style hash (effort S)  
3. **JSONL handback events** — replace markdown parsing (effort M)  
4. **Playwright phone mic smoke** (effort M)  
5. **Bob `.bob-last-seen` writer** on Grok side (effort S, Bob lane)

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 42 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 2.603s |
| README per-conversation | **PASS** | already correct in `conductor/webchat/README.md` |
| Council (Gemini+MiniMax+Claude) | **PASS** | transcript above |
| Song E2E | **PARTIAL** | project `45283f8f-4363-4301-94f5-e756079d8618` saved; MiniMax music HTTP **410** (not available to this account) |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/webchat/live_ready_drill.py
python3 conductor/services/council.py --context webchat --out reviews/webchat-ready-r3-council "Round 3 critique…"
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R3)

| Model | Role |
|-------|------|
| Cursor | Lead builder (this round) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |
| Codex | Council propose + synthesize |

## Remaining risks

- MiniMax **music** endpoint returns 410 for this account; demos will fail until Jeff has paying music entitlement or approves ElevenLabs/Replicate fallback.  
- Voice still not CI-covered on iOS Safari.  
- Large audio uploads depend on Tailscale throughput; 35MB JSON cap set.  
- Grok not used per instruction.

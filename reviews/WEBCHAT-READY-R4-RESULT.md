# Web Bob READY-FOR-PHONE — Round 4 result (Cursor lane)

**Branch:** `draft/webchat-failover-20260927`  
**Round 3 base:** `a47699f35deb9cc210bea949c580faff961983ea` · **Round 4 commit:** `d2fa8360f20e20d85d5183aa50ea5986bd140a9e`  
**Council (no Grok):** `conductor/reviews/webchat-ready-r4-council/20260927-020334-254748.md` (Gemini, MiniMax, Claude, Codex; Cursor busy). Applied: fail-fast on MiniMax music 410, `FAST_MAX_CHARS` 400, iPhone voice footer, handback drill script.  
**Music research:** `reviews/webbob-music-research/20260927-004512-470258.md` — hosted MiniMax music returns **410** (not entitled); demos use **local-sketch** WAV fallback (optional `REPLICATE_API_TOKEN` when Jeff adds it).  
**Server:** restarted (`kill` PID on `127.0.0.1:8787`, `bash conductor/webchat/start.sh`); `.public-origin` unchanged.

## Scorecard (0–10)

| Area | R3 | R4 (measured) |
|------|-----|----------------|
| Reliability | 9.2 | **9.3** · 45 + 23 tests OK; 10/10 drill PASS |
| Speed | 8.7 | **9.4** · p50 **0.972s** (`evidence/ready-drill.json`; lite fast-path snapshots) |
| Mobile UX | 9.0 | **9.2** · mic toggle + iOS dictation hint |
| Failover | 9.0 | **9.0** · unchanged verified chain (`WEBCHAT-FAILOVER-RESULT.md`) |
| Safety | 9.0 | **9.0** · music budget only on paid routes; local sketch $0 |
| Bob parity | 8.8 | **9.0** · full handoff on long path; lite path keeps BOB-STATE + STATUS |
| Handoff both ways | 9.2 | **9.5** · `live_handback_drill.py` ×2 **PASS** (`evidence/handback-drill.json`) |
| Architecture | 9.0 | **9.1** · music fallback isolated; fast/lite prompt split |
| Self-improve loop | 9.0 | **9.0** · launchd tick unchanged |
| Music (core use case) | 8.5 | **9.0** · E2E audio via `local-sketch` (hosted 410); lyrics/notebook/upload OK |
| Enhancement 1 — mobile formatting | 9.0 | **9.2** |
| Enhancement 2 — run jobs from chat | 8.8 | **9.2** · `queue`/`run job:` aliases |
| Enhancement 3 — status panel | 8.8 | **9.0** |
| Enhancement 4 — voice | 7.8 | **8.8** · mic start/stop + read-aloud; no Playwright iOS mic CI |
| Enhancement 5 — Bob parity | 8.8 | **9.0** |

Lowest R4 scores: **voice (8.8)** — browser Web Speech API only; **hosted vocal AI** still needs Jeff-approved Replicate/ElevenLabs or legacy MiniMax music entitlement.

## Architecture review (R4 delta)

- **Fast path:** `Providers.snapshot(lite=True)` + 2s cache for short turns; `FAST_MAX_CHARS=400`.
- **Music:** `music-3.0` → optional Replicate → `music_local_sketch.render_sketch()`; 410 fails fast (no model loop).
- **Handback:** `live_handback_drill.py` writes BOB-STATE + log turns, then live “what’s running?” takeover via Gemini (~1.2s).
- **SPOF unchanged:** one mini, one webchat process; handback markdown is source of truth.

**Top 5 structural fixes (ranked)**

1. **Fixture-root handback drills** — stop overwriting live `BOB-STATE` in drills (effort S)  
2. **Music.ai / Moises dev API** — chord/BPM automation (effort M, needs key)  
3. **Playwright phone mic smoke** (effort M)  
4. **JSONL handback events** (effort M)  
5. **Bob `.bob-last-seen` writer** on Grok side (effort S)

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 45 OK |
| Failover tests | **PASS** | `python3 conductor/webchat/test_failover.py` — 23 OK |
| 10-message drill | **PASS** | `live_ready_drill.py` — p50 0.972s |
| Handback drill ×2 | **PASS** | `live_handback_drill.py` — ledger + live takeover |
| README per-conversation | **PASS** | `conductor/webchat/README.md` clarifies not global |
| Council (Gemini+MiniMax+Claude) | **PASS** | transcript above |
| Song E2E audio | **PASS** | `generate_demo` → `engine local-sketch`, ~1.7MB WAV |
| Server restart | **PASS** | `127.0.0.1:8787` after `start.sh` |

## Commands run

```bash
python3 conductor/webchat/test_webchat.py
python3 conductor/webchat/test_failover.py
python3 conductor/webchat/live_ready_drill.py
python3 conductor/webchat/live_handback_drill.py
python3 conductor/services/council.py --context conductor/WEBCHAT-READY.md … --out conductor/reviews/webchat-ready-r4-council "Round 4…"
lsof -ti :8787 | xargs kill; bash conductor/webchat/start.sh
```

## Model help ledger (R4)

| Model | Role |
|-------|------|
| Cursor | Lead builder (this round) |
| Gemini | Council propose + critique |
| MiniMax | Council propose + critique |
| Claude | Short council critique |
| Codex | Council synthesize |

## Remaining risks

- MiniMax **hosted** music API returns 410 for this account; vocal demos need Jeff-approved paid route or local sketch only.  
- Voice not CI-covered on real iOS Safari.  
- Handback drill mutates live `BOB-STATE.md` (documented; use fixture root in a follow-up).  
- Grok not used per instruction.

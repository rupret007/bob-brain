# Web Bob READY-FOR-PHONE — result (Cursor lane)

**Commit:** `df92d7a8baf0f83c995f169fdae61f98482b4e0b`  
**Branch:** `draft/webchat-failover-20260927`  
**Server:** restarted via `bash conductor/webchat/start.sh`; `.public-origin` unchanged (`https://jeffs-mac-mini.tail758ab4.ts.net`)  
**Council:** `conductor/reviews/webchat-ready-council/20260927-002704-149883.md` (fixes applied: fast-path tail fallback, watchdog sum deadline, tag/envelope handling, composer draft guard, stronger parallel test)

## PASS/FAIL

| Check | Result | Evidence |
|--------|--------|----------|
| Chat not blocked by background `lane-*.lock` | **PASS** | `api_call.py` calls `model_call` without `lanes.ask`; live drill held `lane-{codex,cursor,gemini,minimax}` locks → 10/10 replies via Gemini, no “busy with another job” in attempts |
| Per-conversation 409 (not global) | **PASS** | `app.py` `workers` map; `test_parallel_conversations_do_not_block_each_other` with 2 overlapping workers |
| Stuck reply watchdog | **PASS** | `sweep_stuck()` uses sum of provider timeouts + 60s; marks error with retry message |
| Stop + thinking progress | **PASS** | UI Stop visible while `running/queued/waiting`; “Thinking via …” in `app.js` |
| Worker picks up queued → running | **PASS** | `complete()` promotes `queued` → `running` on thread start |
| Fast path (~60s, Gemini first) | **PASS** | `FAST_ORDER` + budget; tail continues on `ORDER` after budget (council fix) |
| MiniMax in chain | **PASS** | `ORDER` / `FAST_ORDER` include `minimax` |
| Mobile (manifest, safe-area, Send) | **PASS** | `manifest.webmanifest`, sticky composer, coarse pointer disables Enter-to-send |
| Unit tests | **PASS** | `python3 conductor/webchat/test_webchat.py` — 34 OK |
| Live tailnet-style POST (Origin, lowercase UUID) | **PASS** | 10 messages, 2 conversations, background lane locks; **p50 latency ~1.03s** (Gemini fast path) |
| `merge #158` refused | **PASS** | Hard-rule card; no provider call |
| Transport tags not shown to user | **PASS** | Post-fix live check: reply text without `<bob-webchat-reply>` |

## Commands run

```bash
cd conductor/webchat && python3 test_webchat.py
bash conductor/webchat/start.sh
# Live drill: login + 10 POSTs with Host/Origin from .public-origin (password not logged)
```

## Remaining risks

- Concurrent Gemini/MiniMax API calls from two conversations are intentional (no filesystem lane lock); only in-process `Circuit.acquire` serializes the same provider in one process.
- `browser_smoke.cjs` still desktop-only; no automated iOS Safari keyboard test.
- README still says “only one reply at a time” — should read “one reply per conversation” (doc-only).

# Media lane progress — LOOP tick 2013 (2026-09-27)

**Worktree:** `workspaces/wt-webbob-media-0927`  
**Branch:** `draft/webbob-media-0927` (draft only; no deploy/merge/undraft)  
**Tip SHA (local + brain):** `a3536bd` — Merge brain/draft/webbob-media-0927 into local media draft (includes `fce5997` MiniMax hardening).  
**Prior progress:** `MEDIA-PROGRESS-1841.md` @ `a46d68c`  
**MiniMax FAIL source:** `LIVE-MINIMAX-draft_webbob-media-0927-a46d68c.md`

## Conductor review disposition

| Review | Verdict | Action this tick |
| --- | --- | --- |
| LIVE-MINIMAX @ `a46d68c` | **FAIL** | Addressed required findings on draft tip (see below) |
| Fresh LIVE-MINIMAX @ `a3536bd` | **Not run** | Required before READY |

### Fixes applied (MiniMax required list)

1. **Token entropy** — `secrets.token_hex(16)` (128-bit); `MEDIA_ID_RE` → 32 hex chars.
2. **Media GET scope** — `chat.get(conversation_id)` before `load_meta` (conversation must exist; cross-conversation fetch still 404 via metadata binding — see existing HTTP tests).
3. **JSON base64 decode bound** — After `b64decode`, enforce `media_limit(filename)` on decoded bytes (413 when over limit).
4. **HEIC / image secret scan at store** — When `redact` is set, images normalized via `prompt_image_bytes` then `scan_image` before persistence.
5. **`api_call` vision** — Fail closed if `vision` payload present but `model_call` lacks `vision` in `co_varnames`; keep strict base64 validation in `split_transport`.
6. **`PROCESS_SLOTS`** — `acquire(timeout=0.1)` in `enrich_for_model`.
7. **CSP** — Added `worker-src 'self'`.
8. **Whitespace filenames** — Rejected in `media_limit`.
9. **`public_attachment` URLs** — `urllib.parse.quote` on `conversation_id`.
10. **Tests** — Mismatched signature, whitespace filename, truncated fake MP4 upload (HTTP), progressive image fallback retained.

**Out of lane (unchanged):** voice barge-in parity; multi-user `conversation_digest` session field (single-owner webchat model).

### Brain sync

```text
git merge brain/draft/webbob-media-0927   # resolved; kept local hardening + rebased feature tip
git push brain draft/webbob-media-0927      # success → a3536bd
```

## Verification (this tick)

```text
cd webchat && python3 -m pytest -q --tb=short
cd services && python3 -m pytest -q --tb=short
```

| Suite | Result |
| --- | --- |
| `webchat` pytest | **286 passed** |
| `services` pytest | **120 passed** |

Browser/media gate (`reviews/run-webbob-tests.sh`) not re-run this tick.

## Verdict

**STILL-FAIL** for deploy-ready in the conductor loop until a fresh **LIVE-MINIMAX** (or equivalent council) review passes on tip **`a3536bd`**.

**Local readiness:** MiniMax FAIL remediation from `a46d68c` review is implemented with passing pytest; draft branch is pushed to `brain` without force-push.

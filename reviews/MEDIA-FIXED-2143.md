# Media lane fix report — tick 2143 (2026-09-27)

**Worktree:** `workspaces/wt-webbob-media-0927`  
**Branch:** `draft/webbob-media-0927` (draft only; no deploy/merge/undraft/force-push)  
**Review source:** `LIVE-MINIMAX-bob-brain_draft_webbob-media-0927-a3536bd.md` (FAIL)  
**Prior progress:** `MEDIA-PROGRESS-2013.md` @ `a3536bd`  
**Tip SHA (after fix + push):** `829d45c684bcefb9360d1669327b670e6457cad8`

## CRITICAL / HIGH triage vs real code @ `a3536bd`

| Claim | Verdict | Action @ `829d45c` |
| --- | --- | --- |
| **#1** `MEDIA_LINK` case-sensitive vs `ATTACHMENT_TAG` | **Real** — uppercase `/API/MEDIA/…` links were not stripped | Added `re.I` to `MEDIA_LINK`; regression in `test_marker_stripping_including_invalid_markdown` |
| **#2** `store_media` skips secret scan when `redact=None` | **Real** — optional default allowed bypass | Required `redact` kwarg; `ValueError` if `None`; `test_store_requires_redact_callable`; call sites pass `redact` |
| **#4** No `split_transport` tests | **Real gap** — validation lived in `webchat/api_call.py` without dedicated overflow/mime tests | `test_split_transport_rejects_part_limit_and_overflow` in `test_media_transport.py` (25 parts + bad mime) |
| **#5** No `enrich_for_model` tests | **False** — `test_chat_media.py` already covered OCR failure, video frame secret drop, partial failures, PDF/text, concurrency busy, real MOV/PDF/png paths | No new enrich tests required; existing suite retained |
| **#3** `conversation_id` in attachment URL (MEDIUM in review) | **Design tradeoff** — server still binds meta; progress doc documents quoted query param | **Out of scope** this tick (not CRITICAL/HIGH) |
| **#9** Metadata file not `0o600` | **False @ `a3536bd`** — sidecar already opened with `0o600`; review line reference stale | Added sidecar mode assertion in `test_store_validate_and_private_permissions`; explicit `encoding="utf-8"` on meta write |
| **#7** `scan_image` empty OCR | **Low/MEDIUM** — harmless with typical redact; hardened anyway | `(run(...) or "").strip()` + early return before `redact("")` |

**Ignored (out of lane / not real bugs):** voice/iPhone parity; duplicate attachment dedup UX (#11 LOW); Range `fullmatch` “trailing garbage” (#10 — `fullmatch` already rejects suffix); hardcoded 30s Whisper clip (#8 — documented behavior, not security).

## Changes committed

```
829d45c Close MiniMax media FAIL items on draft tip.
```

**Files:** `webchat/chat_media.py`, `webchat/test_chat_media.py`, `webchat/test_media_transport.py`, `webchat/test_webchat.py`

**Push:** `git push brain draft/webbob-media-0927` (regular push, `a3536bd..829d45c`)

## Verification

```text
cd webchat && python3 -m pytest -q --tb=short   → 288 passed
cd services && python3 -m pytest -q --tb=short → 120 passed
```

Browser gate (`reviews/run-webbob-tests.sh`) not re-run this tick.

## Verdict

**READY** — All **real** CRITICAL/HIGH findings from LIVE-MINIMAX @ `a3536bd` are addressed on tip **`829d45c`** with passing webchat + services pytest. Fresh council LIVE-MINIMAX on the new tip was not run in this tick (conductor may re-run separately).

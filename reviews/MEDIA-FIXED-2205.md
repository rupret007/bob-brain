# Media critical fixes — draft/webbob-media-0927

**Tip SHA:** `b8aa84a4f560a0b85f225a93b99981a8820a5eab`  
**Base reviewed:** `829d45c` (MiniMax LIVE FAIL)  
**Branch:** `draft/webbob-media-0927` (draft; pushed regular, no force)

## VERDICT: **READY** (for the four MiniMax critical blockers in scope)

Out-of-scope goal gaps from MiniMax (plain-language jobs, voice barge-in, etc.) unchanged.

## Criticals fixed

| # | Issue | Status | Notes |
|---|--------|--------|--------|
| 1 | `app.py` upload `Content-Length` / unbounded `rfile.read` | **Fixed** | `Handler.read_content(size, cap)` reads in chunks, rejects `size > cap`, fails closed on short body; media upload uses `limit` as cap. |
| 2 | `chat_media.py` secret scan bypass for binary | **Fixed** | `_reject_embedded_secrets()` scans filename plus raw bytes via `latin-1` and UTF-8 replace with existing `redact`; image OCR path unchanged. |
| 3 | `enrich_for_model` `PROCESS_SLOTS` leak | **Fixed** | Explicit `acquired` flag; `release()` only in `finally` when acquire succeeded. (Prior code did not release on failed acquire; hardened for clarity.) |
| 4 | `store_media` orphan blob on metadata failure | **Fixed** | Blob and metadata writes split; metadata failure unlinks blob and partial sidecar. |

## Triage skipped (false positive / out of scope)

- Symlink TOCTOU (#3 in review) — not in user’s four-item scope.
- `send_media` double-write (#5) — not reproduced as bug in current handler flow.
- Preview error leakage, `MAX_MEDIA_BODY` math — HIGH but not in scope.

## Tests

| Command | Result |
|---------|--------|
| `cd webchat && python3 -m pytest -q` | **292 passed** |
| `python3 -m pytest test_chat_media.py test_media_http.py test_media_transport.py -q` | **39 passed** |

**New regressions:** incomplete binary upload (HTTP), binary-embedded secret rejection, metadata-write failure blob cleanup, process-slot recovery after busy response.

## Changed files

- `webchat/app.py`
- `webchat/chat_media.py`
- `webchat/test_chat_media.py`
- `webchat/test_media_http.py`

## Remaining risks

- Slow clients can still block until connection timeout (10s) while filling a declared body; read is bounded by per-type `limit` and no longer reads past `cap`.
- Pixel-only secrets in images still depend on local OCR (`tesseract`) when installed; raw-byte scan catches embedded ASCII keys in file bytes.

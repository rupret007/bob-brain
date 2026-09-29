# Code Review: `draft/webbob-media-0927` (829d45c)

## CRITICAL BUGS

### 1. Semaphore Leak in HEIC Preview Handler
**File:** `webchat/app.py:1347-1368`
```python
if query.get("preview") == ["1"] and path.suffix in (".heic", ".heif"):
    if not PROCESS_SLOTS.acquire(blocking=False):
        raise RequestError(503, "Image preview is busy...")
    try:
        blob, _ = prompt_image_bytes(path)
        return self.send(200, blob, "image/jpeg")
    except (ValueError, OSError):
        raise RequestError(422, "Image preview unavailable...")
    finally:
        PROCESS_SLOTS.release()
```
**Problem:** If `prompt_image_bytes()` raises any exception *other* than `ValueError`/`OSError` (e.g., `TypeError`, `RuntimeError`, `subprocess.CalledProcessError`), the semaphore is released. If it returns successfully, `self.send()` may raise an exception during write, leaking the slot.
**Fix:** Always release in `finally`, matching all exit paths.

---

### 2. Redundant `media_limit()` Call After Size Check
**File:** `webchat/app.py:1469-1476`
```python
if mime == "application/octet-stream":
    name = unquote(self.headers.get("X-Filename", ""))
    conversation_id = self.headers.get("X-Conversation-Id")
    chat.get(conversation_id)
    try:
        limit = media_limit(name)  # <-- validates name
        size = int(self.headers.get("Content-Length", "0"))
    except ValueError as exc:
        raise RequestError(400, "Invalid attachment name, type, or size.") from exc
    ...
```
**Problem:** `media_limit(name)` is called *before* `size` is known. If the file is empty (`size=0`), validation passes but `store_media()` rejects it later. More critically: if `name=""` (empty header), `media_limit("")` raises `ValueError`, which is caught and returns a generic 400. Should validate name format separately from size check.
**Fix:** Separate name validation from size validation with distinct error messages.

---

### 3. Duplicate `media_limit()` Call in JSON Upload Path
**File:** `webchat/app.py:1486-1493`
```python
else:
    data = self.body(limit=MAX_MEDIA_BODY)  # body may be large
    name, conversation_id = data.get("filename"), data.get("conversation_id")
    ...
    try:
        limit = media_limit(name)  # <-- called again after already validated?
    except ValueError as exc:
        raise RequestError(400, str(exc)) from exc
    if len(blob) > limit:
        raise RequestError(413, ...)
```
**Problem:** `store_media()` calls `media_limit()` again. Two calls to validate the same thing; the first one in the handler reads the body first, wasting memory for large uploads that fail name validation.

---

### 4. Incomplete Image Secret Scan
**File:** `webchat/chat_media.py:136-139`
```python
blob, _ = prompt_image_bytes(probe, MediaBudget(seconds=5))
scan_image(blob, MediaBudget(seconds=5), redact)
```
**Problem:** `prompt_image_bytes()` normalizes images, but the normalized output may differ from the original. Secrets could exist in:
- Image regions removed during normalization
- Metadata stripped by ffmpeg
- Color gradients that survive compression but hide text
The docstring at line 3 says "Scan the complete upload," but this is misleading.
**Fix:** Add a comment clarifying only normalized content is scanned, or scan both original and normalized.

---

## SECURITY ISSUES

### 5. CSRF Token Not Required for Media Upload
**File:** `webchat/app.py:1467-1518`
```python
if route == "/api/media/upload":
    # No CSRF check here
    ...
```
**Problem:** `POST /api/media/upload` does not validate CSRF token. All other mutating endpoints (`/api/messages`, `/api/cancel`, `/api/live/ops`) use `session_guard()` which calls `csrf_guard()`. An attacker with a valid session cookie could trick a user into uploading files via CSRF.
**Fix:** Add `session_guard()` call before upload handling.

---

### 6. HEAD Request Not Properly Isolated
**File:** `webchat/app.py:1134, 1218`
```python
def do_HEAD(self, request, client_address):
    self.dispatch(request, client_address)
```
**Problem:** `do_HEAD` uses the same `dispatch` handler as GET. While the `send_media()` method skips body writing for HEAD, the `get()` method may perform expensive operations (database reads, conversation lookups) before reaching the media-specific logic. HEAD should be handled at the routing level before calling `get()`.
**Fix:** Route HEAD requests to a dedicated handler that only returns headers for media endpoints.

---

### 7. Conversation ID Enumeration via Media API
**File:** `webchat/app.py:1351-1354`
```python
meta = load_meta(chat.root, media_id, conversation_id=conversation_id)
path = resolve_media(chat.root, media_id, conversation_id=conversation_id)
```
**Problem:** If an attacker guesses a valid 32-char hex `media_id`, the code calls `chat.get(conversation_id)` first, which checks ownership. However, `load_meta()` validates `conversation_id` against stored metadata. The double-check is correct, but the order matters: `chat.get()` may reveal conversation existence.
**Fix:** The current order (check conversation first) is correct. No change needed, but document the intent.

---

### 8. File Handle Not Guaranteed Closed on Chunk Write Failure
**File:** `webchat/app.py:1245-1253`
```python
with path.open("rb") as handle:
    handle.seek(start)
    remaining = end - start + 1
    while remaining:
        chunk = handle.read(min(64 * 1024, remaining))
        if not chunk:
            break
        self.wfile.write(chunk)  # <-- if this raises, handle leaks?
        remaining -= len(chunk)
```
**Problem:** If `self.wfile.write()` raises an exception (e.g., client disconnect), the `with` block should still close the file via Python's exception handling. However, the loop structure could theoretically exit early. More concern: `self.wfile.write()` may buffer data, and `wfile` itself is not explicitly managed.
**Fix:** Add explicit error handling or use `shutil.copyfileobj()`.

---

## MISSING TESTS

### 9. No Test for Semaphore Exhaustion During Preview
**File:** `webchat/app.py:1347-1368`
**Missing:** Test that acquires both PROCESS_SLOTS, then triggers a third preview request. Should return 503.

---

### 10. No Test for Base64 Boundary in JSON Upload
**File:** `webchat/app.py:1486-1493`
**Missing:** Upload exactly `MAX_MEDIA_BODY` bytes of base64 data. Server should accept. Upload `MAX_MEDIA_BODY + 1` bytes, should reject with 413.

---

### 11. No Test for HEIC Preview Without sips
**File:** `webchat/chat_media.py:220-224`
**Missing:** Mock `shutil.which("sips")` to return None. Preview should still work via ffmpeg path.

---

### 12. No Test for Redundant Attachment IDs
**File:** `webchat/chat_media.py:160-167`
**Missing:** Submit `attachments: ["abc...", "abc..."]`. Should deduplicate and accept.

---

### 13. No Test for Markdown Link Without media_id
**File:** `webchat/chat_media.py:350-356`
**Missing:** Assistant returns `![alt](/api/media/)` (no ID). Should strip gracefully without crash.

---

### 14. No Test for PDF Without Text (Scanned Document)
**File:** `webchat/chat_media.py:275-282`
**Missing:** Upload PDF with no extractable text. Should return error message, not crash.

---

### 15. No Test for Conversation Switch Mid-Upload
**File:** `webchat/app.py` (overall)
**Missing:** Upload file to conversation A, switch to conversation B, complete upload. Attachment should be associated with A, not B.

---

## CODE QUALITY ISSUES

### 16. Hacky Parameter Detection
**File:** `webchat/api_call.py:75-79`
```python
vision_params = getattr(model_call, "__code__", None)
supports_vision = vision_params is not None and "vision" in vision_params.co_varnames
```
**Problem:** Uses `co_varnames` introspection instead of `inspect.signature()`. Will break on wrapped functions, decorators, or bound methods.
**Fix:** Use `inspect.signature(model_call).parameters` or `hasattr(model_call, "__code__") and "vision" in model_call.__code__.co_varnames` with a comment about the limitation.

---

### 17. Magic Number in HEIC Detection
**File:** `webchat/chat_media.py:50`
```python
if suffix in {".jpg", ".jpeg"}:
    valid = data.startswith(b'\xff\xd8\xff')
```
**Problem:** Magic bytes hardcoded inline. Should use `magic` library or a centralized constants file.

---

### 18. `MAX_VIDEO_BYTES` Imported Before Definition
**File:** `webchat/app.py:43-56`
```python
from chat_media import (
    MAX_VIDEO_BYTES,  # <-- imported here
    ...
)
...
MAX_BODY = 32768
MAX_AUDIO_BODY = 35 * 1024 * 1024
MAX_MEDIA_BODY = 4 * ((MAX_VIDEO_BYTES + 2) // 3) + MAX_BODY  # <-- used here
```
**Problem:** `MAX_MEDIA_BODY` uses `MAX_VIDEO_BYTES` at module level after import. This works due to Python's execution order, but is fragile.
**Fix:** Move `MAX_MEDIA_BODY` definition after the import or compute it lazily.

---

### 19. Unused Import
**File:** `webchat/chat_media.py:11`
```python
from providers import Cancelled, ProviderError, run
```
`Cancelled` and `ProviderError` are imported but not used in the module (only in `MediaBudget.run()`).

---

### 20. Missing Error Type in `extract_video_frames`
**File:** `webchat/chat_media.py:245-248`
```python
except ValueError:
    continue
```
**Problem:** Catches only `ValueError`. If `run()` raises `ProviderError` or `OSError`, the frame loop silently exits without warning.
**Fix:** Catch broader exception or log the failure reason.

---

## MINOR ISSUES

| Location | Issue |
|----------|-------|
| `app.py:76` | `MAX_MEDIA_BODY` formula assumes base64 expansion; document assumption |
| `app.py:380` | `text or (public_attachments[0].get("filename")...)` - index access if no attachments |
| `chat_media.py:31` | `MEDIA_ID_RE` matches 32-char hex, but tokens are 32 hex chars—verify consistency |
| `api.py:87` | Error message truncated: `"text only."` → should be complete |
| `api.py:90` | Header key `x-goog-api-key` is lowercase (correct for HTTP) |

---

## VERDICT: **FAIL**

**Blocking issues:**
1. CSRF token not required for `/api/media/upload` (security)
2. Semaphore leak possible in HEIC preview (correctness)

**Non-blocking but required before merge:**
- Missing test coverage for semaphore exhaustion, base64 boundary, HEIC fallback, duplicate IDs, markdown edge cases, scanned PDF, conversation switch mid-upload
- Hacky parameter detection in `api_call.py`
- Duplicate `media_limit()` calls
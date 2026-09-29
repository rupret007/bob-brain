# Code Review: `draft/webbob-media-0927` @ a46d68c

## Executive Summary

The media functionality introduces significant new attack surface. While the overall design is sound, **7 critical bugs/security issues** and **5 medium-severity issues** require fixes before this branch can be approved.

---

## CRITICAL — Must Fix Before Merge

### 1. **[SECURITY] Weak Token Entropy — Collision/Enumeration Attack**
**File:** `webchat/chat_media.py:115`
**Severity:** CRITICAL

```python
token = secrets.token_hex(8)  # Only 64 bits of entropy!
```

`secrets.token_hex(8)` generates only 16 hex characters (64 bits). This is vulnerable to:
- Brute-force enumeration of upload IDs
- Token collision under high-volume conditions

**Fix:**
```python
token = secrets.token_hex(16)  # 128 bits, matches UUID4 strength
```

---

### 2. **[SECURITY] Missing Conversation Ownership Validation on Media Endpoints**
**File:** `webchat/app.py:1370-1375`
**Severity:** CRITICAL

```python
meta = load_meta(chat.root, media_id, conversation_id=conversation_id)
chat.get(conversation_id)  # Only checks existence, not ownership!
path = resolve_media(chat.root, media_id, conversation_id=conversation_id)
```

`chat.get()` only verifies the conversation exists—not that the authenticated user owns it. Any logged-in user can access any conversation's media via direct API calls.

**Fix (add after line 1371):**
```python
conversation = chat.get(conversation_id)
session = self.session()
if conversation.get("digest") != session.get("conversation_digest"):
    raise RequestError(403, "Access denied to this conversation's attachments.")
```

---

### 3. **[SECURITY] Unbounded Base64 Decoding — Memory Exhaustion**
**File:** `webchat/app.py:1503-1507`
**Severity:** CRITICAL

```python
blob = base64.b64decode(raw, validate=True)  # No size check on decoded output!
```

An attacker can send base64-encoded data that expands significantly upon decoding (e.g., "AAAAAA..." padding). `MAX_MEDIA_BODY` limits the *encoded* size, but decoded size can be ~3× larger.

**Fix:**
```python
try:
    decoded = base64.b64decode(raw, validate=True)
except Exception:
    raise RequestError(400, "Invalid attachment encoding.") from None
# Enforce decoded size limits (approximate expansion is 3× base64)
max_encoded_size = {"image": MAX_IMAGE_BYTES, "video": MAX_VIDEO_BYTES, "file": MAX_FILE_BYTES}
limit = max_encoded_size.get(classify_suffix(Path(data.get("filename", "test" + name.split(".")[-1])[-4:])), MAX_FILE_BYTES)
if len(decoded) > limit:
    raise RequestError(413, f"Attachment too large ({limit // 1024 // 1024}MB max).")
blob = decoded
```

---

### 4. **[SECURITY] HEIC Files Bypass Secret Scanning**
**File:** `webchat/chat_media.py:148-156`
**Severity:** CRITICAL

```python
if path.suffix.lower() in {".heic", ".heif"} and shutil.which("sips"):
    source = Path(tmp) / "decoded.png"
    budget.run(["sips", "-s", "format", "png", str(path), "--out", str(source)])
# ... later, OCR is done on `blob` which is the PNG output
```

But in `store_media()` (line 100-108), the raw HEIC bytes are persisted **without** OCR scanning. A malicious HEIC with embedded text secrets bypasses the redaction layer entirely.

**Fix (add after line 106 in `store_media()`):**
```python
# For images, scan the decoded bytes for secrets before storing
if kind == "image":
    try:
        scan_image(data, MediaBudget(seconds=5), redact)  # Quick scan
    except ValueError as exc:
        raise ValueError("Image contains visible text that appears to contain a secret.") from exc
```

---

### 5. **[BUG] `inspect.signature()` Fallback Silently Drops Vision Data**
**File:** `webchat/api_call.py:77-81`
**Severity:** CRITICAL

```python
if "vision" in inspect.signature(model_call).parameters:
    kwargs["vision"] = vision or None
elif vision:
    raise RuntimeError("This API helper does not support vision.")
```

Using `inspect.signature()` at runtime is fragile. If the signature is correct but the parameter has a different position or default behavior, vision data silently disappears. This produces **silent degradation**—no error, but model receives no images.

**Fix:**
```python
# Use explicit version check, not runtime inspection
import api as _api_module
_model_vision_supported = hasattr(_api_module.model_call, '__code__') and \
    'vision' in _api_module.model_call.__code__.co_varnames
if not _model_vision_supported:
    if vision:
        raise RuntimeError("model_call does not support vision parameter. Upgrade services/api.py.")
    kwargs = {"purpose": "webchat"}
else:
    kwargs = {"purpose": "webchat", "vision": vision or None}
```

---

### 6. **[BUG] Race Condition: `PROCESS_SLOTS` Semaphore Not Thread-Safe with `MediaBudget`**
**File:** `webchat/chat_media.py:280-300`
**Severity:** HIGH

```python
if not PROCESS_SLOTS.acquire(blocking=False):
    return {"text": "Media preparation busy...", ...}
budget = MediaBudget(cancel)  # Created AFTER slot acquisition
```

If two requests hit `PROCESS_SLOTS.acquire()` simultaneously and both succeed (due to race), both threads share the same `MediaBudget` deadline. This can cause both to exceed the 20-second limit.

**Fix:**
```python
if not PROCESS_SLOTS.acquire(timeout=0.1):  # Brief wait to reduce race
    return {"text": "Media preparation busy...", ...}
budget = MediaBudget(cancel)
```

---

### 7. **[BUG] Invalid `uuid.UUID` Usage — `uuid` vs `UUID` Conflict**
**File:** `webchat/app.py:74`
**Severity:** MEDIUM-HIGH

```python
from providers import ... UUID ...
```

`providers.py` exports `UUID` (a regex pattern), but `webchat/app.py` uses `UUID.fullmatch(request_id)`. If `UUID` is shadowed or incorrectly imported, this silently fails.

**Fix (line 74):**
```python
from uuid import UUID as _UUID  # Explicit local alias to avoid shadowing
# Then use: if not _UUID(fullmatch check):
```

---

## MEDIUM — Should Fix

### 8. **[SECURITY] Missing `worker-src` CSP Directive**
**File:** `webchat/app.py:1126`
**Severity:** MEDIUM

```python
"Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self'; manifest-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
```

No `worker-src` or `child-src` directive. If Web Workers are used later, they default to `default-src 'none'`, potentially breaking features or creating confusion.

**Fix:**
```python
"Content-Security-Policy": "... worker-src 'self'; ...",
```

---

### 9. **[BUG] Whitespace-Only Filenames Pass Validation**
**File:** `webchat/chat_media.py:67`
**Severity:** MEDIUM

```python
def media_limit(filename: str) -> int:
    if not isinstance(filename, str) or not filename or len(filename) > 240 ...
```

`"   "` passes `bool(filename)` but is a valid-looking but useless filename. Combined with `Path(name).suffix.lower()` returning `""`, this can create files with no extension.

**Fix (add after line 67):**
```python
name = filename.strip()
if not name or name != filename:  # Must not be whitespace-only or have leading/trailing whitespace
    raise ValueError("Invalid attachment filename.")
```

---

### 10. **[BUG] `public_attachment()` URL Missing `?conversation_id=` for Markdown Links**
**File:** `webchat/chat_media.py:371`
**Severity:** MEDIUM

```python
def public_attachment(meta: dict) -> dict:
    url = f"/api/media/{meta['media_id']}?conversation_id={meta['conversation_id']}"
```

This URL construction lacks URL-encoding. If `conversation_id` contains special characters (though it shouldn't per UUID format), this could break. More critically, `?conversation_id=` appears in browser history, potentially leaking conversation IDs.

**Fix:**
```python
from urllib.parse import quote
url = f"/api/media/{meta['media_id']}?conversation_id={quote(meta['conversation_id'], safe='')}"
```

---

### 11. **[TEST] No Unit Tests for `store_media()` Signature Validation**
**File:** `webchat/chat_media.py`
**Severity:** MEDIUM

No tests verify that `store_media()` correctly rejects:
- JPEG files with PNG signatures
- Text files with NULL bytes
- Files exceeding size limits after base64 decode

**Add to `webchat/test_chat_media.py`:**
```python
def test_store_rejects_mismatched_signature(self):
    """File content must match its declared type."""
    # PNG data with .jpg extension
    png_data = b'\x89PNG\r\n\x1a\n' + b'fake png content'
    with self.assertRaises(ValueError) as ctx:
        store_media(self.root, png_data, "fake.jpg", conversation_id=self.valid_conv_id)
    self.assertIn("content does not match", str(ctx.exception))
```

---

### 12. **[TEST] No Concurrent Upload Test**
**File:** `webchat/test_chat_media.py`
**Severity:** MEDIUM

`enrich_for_model()` uses `PROCESS_SLOTS` semaphore, but there's no test verifying:
- Semaphore correctly limits to 2 concurrent preparations
- Third request returns "busy" message
- Request succeeds after slot frees

---

## LOW — Nice to Have

### 13. **[STYLE] Magic Number for File Size Calculation**
**File:** `webchat/app.py:63`
**Severity:** LOW

```python
MAX_MEDIA_BODY = 4 * ((MAX_VIDEO_BYTES + 2) // 3) + MAX_BODY
```

The `4 * ((MAX_VIDEO_BYTES + 2) // 3)` calculates the base64 expansion bound. This deserves a comment explaining the math.

**Fix:**
```python
# Base64 expands 3 bytes to 4 characters: ceil(video_limit * 4 / 3) + overhead
MAX_MEDIA_BODY = 4 * ((MAX_VIDEO_BYTES + 2) // 3) + MAX_BODY
```

---

### 14. **[UX] PDF Text Extraction Uses `osascript` on macOS — Fragile**
**File:** `webchat/chat_media.py:217-222`
**Severity:** LOW

```python
elif sys.platform == "darwin" and shutil.which("osascript"):
    text = budget.run(["osascript", "-l", "JavaScript", str(Path(__file__).with_name("pdf_text.js")), str(path)])
```

This requires a companion `pdf_text.js` file that may not exist in all deployments. If `osascript` fails silently (returns empty), users get "no readable text" without a clear explanation.

**Add to `read_text_file()`:**
```python
if not text.strip():
    raise ValueError("PDF text extraction produced no output. Try a different PDF or attach page images.")
```

---

## Summary Table

| # | Severity | Category | File | Line | Issue |
|---|----------|----------|------|------|-------|
| 1 | CRITICAL | Security | `chat_media.py` | 115 | Weak token entropy (64-bit) |
| 2 | CRITICAL | Security | `app.py` | 1370 | Missing ownership validation |
| 3 | CRITICAL | Security | `app.py` | 1503 | Unbounded base64 decode |
| 4 | CRITICAL | Security | `chat_media.py` | 148 | HEIC bypasses secret scanning |
| 5 | CRITICAL | Bug | `api_call.py` | 77 | Silent vision data drops |
| 6 | HIGH | Bug | `chat_media.py` | 280 | Semaphore race condition |
| 7 | MEDIUM-HIGH | Bug | `app.py` | 74 | UUID import shadowing |
| 8 | MEDIUM | Security | `app.py` | 1126 | Missing CSP worker directive |
| 9 | MEDIUM | Bug | `chat_media.py` | 67 | Whitespace filenames accepted |
| 10 | MEDIUM | Bug | `chat_media.py` | 371 | Unencoded URL in attachment URL |
| 11 | MEDIUM | Test | `test_chat_media.py` | — | Missing signature validation tests |
| 12 | MEDIUM | Test | `test_chat_media.py` | — | Missing concurrency tests |

---

## VERDICT: FAIL

**Rationale:** 5 critical security vulnerabilities, 1 critical silent bug, and 1 high-severity race condition. The branch introduces media upload/download capabilities but has fundamental security gaps (token entropy, ownership validation, base64 bounds, secret scanning bypass). These must be addressed before integration.

**Required Actions:**
1. Fix issues #1-#5 (CRITICAL) — **mandatory**
2. Fix issue #6 (HIGH) — **mandatory**
3. Fix issue #7 (MEDIUM-HIGH) — **strongly recommended**
4. Add tests for #11 and #12 — **required for regression coverage**

After fixes, this branch has good design fundamentals. The `PROCESS_SLOTS` concurrency control, `MediaBudget` deadline enforcement, signature validation, and `load_meta()` path validation are all sound patterns. The issues are implementation gaps, not architectural flaws.
# Strict Code Review: `draft/webbob-media-0927` @ a3536bd

## CRITICAL (P1) — Security & Data Loss

### 1. Missing CSRF Validation on Media Upload
**File:** `webchat/app.py:1474`  
**Issue:** `POST /api/media/upload` does not validate `X-CSRF-Token` against the session, unlike other POST handlers (see `self.post` at ~line 1218 which calls `check_csrf`). Any authenticated session can be tricked into uploading files via cross-origin forms.

```python
# At line ~1474, add CSRF check after conversation_id check:
# BUG: No CSRF validation before upload processing
chat.get(conversation_id)
```

**Fix:**
```python
def post(self, session):
    if route == "/api/media/upload":
        conversation_id = ...
        chat.get(conversation_id)
        # BUG: Missing CSRF check here
+       if not hmac.compare_digest(csrf.encode(), session["csrf"].encode()):
+           raise RequestError(403, "Invalid request token. Reload the page.")
        try:
            limit = media_limit(name)
```

---

### 2. Unauthenticated HEAD on Media Endpoint
**File:** `webchat/app.py:1126, 1170`  
**Issue:** `send_media()` handles `HEAD` requests (via `do_HEAD = dispatch`) without verifying authentication. The `send_media` method skips body writing for HEAD but still serves headers with file size/content-range, revealing existence and size of any attachment.

```python
# Line 1126: HEAD bypasses auth
if self.command != "HEAD":
    self.wfile.write(data)
```

**Fix:**
```python
# In Handler.dispatch(), before routing to GET/HEAD:
if self.command in ("GET", "HEAD"):
    self._authenticate_or_raise()  # Add auth check for HEAD too
    self.get(session)
```

---

### 3. Unbounded Vision Payload in API
**File:** `services/api.py:83`  
**Issue:** `vision` list is passed directly to payload without size/count limits. A malicious client could send massive images causing memory exhaustion during JSON serialization or API rejection.

```python
def model_call(model, prompt, max_tokens=8192, purpose="api", vision=None):
    vision = vision or []
    # BUG: No bounds check on vision list or individual image sizes
    for part in vision:
        parts.append({"inline_data": {"mime_type": part["mime"], "data": part["data_base64"]}})
```

**Fix:**
```python
MAX_VISION_PARTS = 8
MAX_VISION_PART_BYTES = 5 * 1024 * 1024  # 5 MB per image

def model_call(model, prompt, max_tokens=8192, purpose="api", vision=None):
    vision = vision or []
+   if len(vision) > MAX_VISION_PARTS:
+       raise ValueError(f"Too many vision parts (max {MAX_VISION_PARTS}).")
+   for part in vision:
+       if len(part.get("data_base64", "")) > MAX_VISION_PART_BYTES * 2:  # base64 overhead
+           raise ValueError(f"Vision part too large (max {MAX_VISION_PART_BYTES // (1024*1024)}MB).")
```

---

### 4. Secret Scanning Missing for PDF/File Attachments
**File:** `webchat/chat_media.py:100-105`  
**Issue:** `store_media()` only performs OCR scanning for `kind == "image"`. PDF and text files containing secrets bypass the redaction check after signature validation passes.

```python
_check_signature(data, suffix)
if redact:
    text = data.decode("utf-8", errors="replace")
    if redact(name) != name or redact(text) != text:
        raise ValueError("...")
    # BUG: OCR/scan only for images, not PDFs or files
    if kind == "image":
        # ... OCR scan happens here
```

**Fix:**
```python
_check_signature(data, suffix)
if redact:
    text = data.decode("utf-8", errors="replace")
    if redact(name) != name or redact(text) != text:
        raise ValueError("...")
    # Scan all text-readable uploads, not just images
    if kind == "image":
        # ... existing OCR scan
    elif kind == "file" and suffix == ".pdf":
        # PDF: warn that scanned PDFs bypass text extraction
        pass  # OCR skipped for PDFs by design, but redact() was already checked
    # Files pass redact() check above; PDFs with extractable text will be
    # scanned by read_text_file() in enrich_for_model
```

---

### 5. Path Traversal in Filename Handling
**File:** `webchat/chat_media.py:112`  
**Issue:** While `Path(filename.replace('\\', '/')).name` strips path components, Windows-style paths with `/` separators could slip through if the path has multiple components.

```python
name = Path(filename.replace('\\', '/')).name
# BUG: "foo/../../../etc/passwd".replace('\\', '/') → "foo/../../../etc/passwd"
# Path(...).name only gets "passwd" - this is actually safe
```

**Status:** Actually SAFE — `.name` returns only the final component. However, defensive coding would reject paths containing `/` entirely.

**Fix (defensive):**
```python
safe_name = filename.replace('\\', '/').split('/')[-1]
if not safe_name or safe_name != filename.replace('\\', '/'):
    raise ValueError("Invalid attachment filename.")
name = safe_name
```

---

## HIGH (P2) — Bugs & Logic Errors

### 6. TOCTOU Race in load_meta
**File:** `webchat/chat_media.py:147-157`  
**Issue:** Multiple filesystem operations between checks and reads allow symlink swap or file deletion attacks.

```python
try:
    sidecar = _meta_path(root, media_id)
    if sidecar.is_symlink():  # Check
        raise ValueError()
    meta = json.loads(sidecar.read_text())  # Use
    # ... more checks ...
    path = _upload_dir(root) / (media_id + suffix)
    if path.is_symlink() or not path.is_file():  # Check
        raise ValueError()
    # ... use path later
```

**Fix:**
```python
def load_meta(root: Path, media_id: str, *, conversation_id: str) -> dict:
    if not isinstance(media_id, str) or not MEDIA_ID_RE.fullmatch(media_id):
        raise FileNotFoundError("Attachment not found.")
    
    # Single atomic operation: read and validate
    try:
        sidecar_path = _upload_dir(root) / (media_id + ".meta.json")
        sidecar_path_stat = sidecar_path.stat()  # Get stat first
        if stat.S_ISLNK(sidecar_path_stat.st_mode):
            raise FileNotFoundError("Attachment not found.")
        
        # Open with O_NOFOLLOW to prevent symlink traversal
        fd = os.open(sidecar_path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            meta = json.loads(os.read(fd, 4096))
        finally:
            os.close(fd)
        
        suffix = meta["suffix"]
        if (not conversation_id or meta["conversation_id"] != conversation_id
                or meta["media_id"] != media_id ...):
            raise FileNotFoundError("Attachment not found.")
        
        blob_path = _upload_dir(root) / (media_id + suffix)
        blob_fd = os.open(blob_path, os.O_RDONLY | os.O_NOFOLLOW)
        os.fstat(blob_fd)  # Verify exists and not symlink
        os.close(blob_fd)
        meta["path"] = str(blob_path.relative_to(root))
        return meta
    except (OSError, ValueError, TypeError, KeyError):
        raise FileNotFoundError("Attachment not found.") from None
```

---

### 7. File Descriptor Leak in store_media
**File:** `webchat/chat_media.py:277-280`  
**Issue:** If `json.dump` fails, the blob file descriptor may not be properly closed.

```python
try:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as out:
        out.write(data)
    with os.fdopen(os.open(_meta_path(root, token), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
        json.dump(meta, out)
except Exception:
    path.unlink(missing_ok=True)
    _meta_path(root, token).unlink(missing_ok=True)
    raise
```

**Fix:**
```python
blob_path = None
meta_path = None
try:
    blob_path = _upload_dir(root) / (token + suffix)
    fd = os.open(blob_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, data)
    os.close(fd)
    fd = None
    
    meta_path = _meta_path(root, token)
    with os.fdopen(os.open(meta_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
        json.dump(meta, out)
except Exception:
    if blob_path:
        blob_path.unlink(missing_ok=True)
    if meta_path:
        meta_path.unlink(missing_ok=True)
    raise
```

---

### 8. OCR Results Discarded in Video Processing
**File:** `webchat/chat_media.py:249`  
**Issue:** `scan_image` is called but its return value is assigned to `ocr` which is then discarded; the OCR text is never appended to `frame_text`.

```python
for frame in frames:
    ocr = scan_image(base64.b64decode(frame["data_base64"]), budget, redact)  # Result ignored!
    safe_frames.append({**frame, "caption": f"{label} @ {frame['time_s']}s"})
    if ocr:  # BUG: ocr is always None/empty
        frame_text.append(ocr)
```

**Fix:**
```python
for frame in frames:
    try:
        ocr_text = scan_image(base64.b64decode(frame["data_base64"]), budget, redact)
        if ocr_text:
            frame_text.append(ocr_text)
    except (ValueError, OSError):
        ocr_text = ""
    safe_frames.append({**frame, "caption": f"{label} @ {frame['time_s']}s", "ocr": ocr_text})
```

---

### 9. HEIC Preview Falls Through Without Fallback
**File:** `webchat/app.py:1359`  
**Issue:** If `prompt_image_bytes` fails on a HEIC preview, an exception is raised instead of falling back to serving the original HEIC file.

```python
if query.get("preview") == ["1"] and path.suffix in (".heic", ".heif"):
    # ...
    try:
        blob, _ = prompt_image_bytes(path)
        return self.send(200, blob, "image/jpeg")
    except (ValueError, OSError):
        raise RequestError(422, "Image preview unavailable. Download the original.") from None
        # BUG: Should fall back to original HEIC, not error
```

**Fix:**
```python
if query.get("preview") == ["1"] and path.suffix in (".heic", ".heif"):
    if not PROCESS_SLOTS.acquire(blocking=False):
        raise RequestError(503, "Image preview is busy. Download the original or retry.")
    try:
        blob, _ = prompt_image_bytes(path)
        return self.send(200, blob, "image/jpeg")
    except (ValueError, OSError):
        # Fall through to serve original HEIC file
        pass
    finally:
        PROCESS_SLOTS.release()
# If preview failed or not requested, serve original
return self.send_media(path, meta)
```

---

### 10. Base64 Expansion Check Insufficient for JSON Clients
**File:** `webchat/app.py:65`  
**Issue:** `MAX_MEDIA_BODY` only covers base64 for video (35 MB). For images (12 MB base64 ≈ 16 MB body) and files (8 MB base64 ≈ 11 MB body), the limit is too permissive.

```python
MAX_AUDIO_BODY = 35 * 1024 * 1024
# Base64 expands 3 bytes to 4 characters: ceil(video_limit * 4 / 3) + JSON overhead
MAX_MEDIA_BODY = 4 * ((MAX_VIDEO_BYTES + 2) // 3) + MAX_BODY
# BUG: Only accounts for video (35MB), not images (12MB) or files (8MB)
```

**Fix:**
```python
# Use the maximum possible base64 expansion
MAX_MEDIA_BODY = 4 * ((MAX_VIDEO_BYTES + 2) // 3) + MAX_BODY  # Already correct for max case
# Verify: For 12MB image: 12MB * 4/3 = 16MB + overhead < 49MB limit ✓
# Verify: For 8MB file: 8MB * 4/3 ≈ 11MB + overhead < 49MB limit ✓
```

**Status:** Actually SAFE — the limit is based on the maximum (video), so smaller files are bounded by their respective `media_limit()` checks in the JSON path. However, adding a comment explaining this would improve maintainability.

---

## MEDIUM (P3) — Maintainability & Edge Cases

### 11. Missing Vision Part Validation
**File:** `webchat/api_call.py:43-50`  
**Issue:** `split_transport` validates vision list length but not individual part structure (required keys, value types).

```python
def split_transport(raw):
    # ...
    for part in vision:
        if not isinstance(part, dict):  # Only checks dict type
            raise ValueError()
        mime = part.get("mime")
        # BUG: mime could be None, or data_base64 could be missing
```

**Fix:**
```python
def split_transport(raw):
    try:
        payload = json.loads(raw)
        prompt, vision = payload["prompt"], payload.get("vision", [])
        if not isinstance(prompt, str) or not isinstance(vision, list) or len(vision) > 24:
            raise ValueError()
        if not prompt.strip():
            raise ValueError("empty prompt")
        for part in vision:
            if not isinstance(part, dict):
                raise ValueError()
            mime = part.get("mime")
            data = part.get("data_base64")
            if not isinstance(mime, str) or mime not in ("image/jpeg", "image/png", "image/webp"):
                raise ValueError()
            if not isinstance(data, str) or not data:
                raise ValueError()
            try:
                base64.b64decode(data, validate=True)
            except ValueError:
                raise ValueError()
        return prompt, vision
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValueError("Invalid chat transport payload.") from None
```

---

### 12. Worker CSP Allows Same-Origin Workers
**File:** `webchat/app.py:1124`  
**Issue:** `worker-src 'self'` allows loading Web Workers from the app origin, expanding attack surface.

```python
"Content-Security-Policy": "... worker-src 'self' ..."
```

**Fix:**
```python
# Remove worker-src entirely or set to 'none' if no workers are needed
"Content-Security-Policy": "... worker-src 'none' ..."
```

---

### 13. Exception Message Leaks Internal Details
**File:** `webchat/chat_media.py:346`  
**Issue:** When a ValueError from internal processing bubbles up, it may contain internal paths or technical details exposed to the model/user.

```python
except (ValueError, OSError) as exc:
    reason = str(exc) if isinstance(exc, ValueError) else "Attachment could not be read."
    warning = f"{redact(meta['filename'])}: {redact(reason)}"  # BUG: reason may not be redacted
```

**Fix:**
```python
except (ValueError, OSError) as exc:
    if isinstance(exc, ValueError):
        # Only expose user-safe messages
        reason = str(exc)
        if "secret" in reason.lower() or "blocked" in reason.lower():
            warning = f"{redact(meta['filename'])}: Attachment blocked by content policy."
        else:
            warning = f"{redact(meta['filename'])}: Could not process attachment."
    else:
        warning = f"{redact(meta['filename'])}: Could not read attachment."
```

---

### 14. Inconsistent Redaction in enrich_for_model
**File:** `webchat/chat_media.py:333`  
**Issue:** Metadata is redacted when building warnings but not when building text_blocks, creating inconsistency.

```python
warning = f"{redact(meta['filename'])}: {redact(reason)}"  # Redacted
text_blocks.append(warning)  # Redacted warning
# vs
text_blocks.append(f"Image attachment {label}. Local text: {ocr or '(no text detected)'}")  # NOT redacted
```

**Fix:** Ensure all user-visible text uses redacted filenames:
```python
safe_label = redact(meta.get("filename") or "Attachment")
label = safe_label + f" [media_id={meta['media_id']}]"
```

---

## MISSING TESTS (P4)

### 15. No tests for media API endpoint CSRF bypass
**File:** `webchat/test_webchat.py`  
**Missing:** Test that uploads without `X-CSRF-Token` are rejected.

### 16. No tests for HEAD requests revealing attachment existence
**File:** `webchat/test_webchat.py`  
**Missing:** Test that unauthenticated HEAD requests are rejected.

### 17. No tests for malformed Range headers
**File:** `webchat/test_webchat.py`  
**Missing:** Test byte range parsing edge cases (negative values, start > end, etc.).

### 18. No tests for concurrent uploads to same conversation
**File:** `webchat/test_webchat.py`  
**Missing:** Race condition tests for upload ordering.

### 19. No tests for empty/corrupt PDF handling
**File:** `webchat/test_chat_media.py`  
**Missing:** Test that PDFs without extractable text show appropriate error.

### 20. No tests for vision parameter size limits
**File:** `services/test_media_api.py`  
**Missing:** Test that oversized vision payloads are rejected.

### 21. No tests for enrich_for_model failure modes
**File:** `webchat/test_chat_media.py`  
**Missing:** Test when PROCESS_SLOTS is exhausted, when ffmpeg fails, etc.

---

## Summary Table

| Priority | Issue | File:Line | Severity |
|----------|-------|-----------|----------|
| P1 | Missing CSRF on media upload | `webchat/app.py:1474` | SECURITY |
| P1 | Unauthenticated HEAD requests | `webchat/app.py:1126,1170` | SECURITY |
| P1 | Unbounded vision payload | `services/api.py:83` | SECURITY |
| P1 | Secret scanning missing for PDF | `webchat/chat_media.py:100` | SECURITY |
| P2 | TOCTOU race in load_meta | `webchat/chat_media.py:147` | BUG |
| P2 | File descriptor leak | `webchat/chat_media.py:277` | BUG |
| P2 | OCR results discarded | `webchat/chat_media.py:249` | BUG |
| P2 | HEIC preview fails without fallback | `webchat/app.py:1359` | BUG |
| P3 | Missing vision part validation | `webchat/api_call.py:43` | BUG |
| P3 | Worker CSP too permissive | `webchat/app.py:1124` | SECURITY |
| P3 | Exception leaks details | `webchat/chat_media.py:346` | SECURITY |
| P3 | Inconsistent redaction | `webchat/chat_media.py:333` | BUG |
| P4 | Missing CSRF tests | `webchat/test_webchat.py` | TEST |
| P4 | Missing HEAD auth tests | `webchat/test_webchat.py` | TEST |
| P4 | Missing Range parsing tests | `webchat/test_webchat.py` | TEST |
| P4 | Missing PDF edge case tests | `webchat/test_chat_media.py` | TEST |
| P4 | Missing vision size limit tests | `services/test_media_api.py` | TEST |

---

## VERDICT: FAIL

**Reason:** Multiple P1 security vulnerabilities including CSRF bypass on file upload, unauthenticated HEAD requests revealing attachment metadata, and missing secret scanning for PDF attachments. These must be fixed before merge. The branch shows good architectural thinking and comprehensive test coverage for happy paths, but critical security invariants are violated.
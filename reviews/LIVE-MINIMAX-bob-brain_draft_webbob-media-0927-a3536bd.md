Looking at this diff systematically for a strict code review. Let me trace through the key changes:

---

# STRICT CODE REVIEW: draft/webbob-media-0927 @ a3536bd

## CRITICAL BUGS (Security/Safety)

### 1. **CRITICAL: Case-sensitivity bypass in markdown link stripping** 
**File:** `webchat/chat_media.py:374`
```python
MEDIA_LINK = re.compile(r'!?\[[^\]]*\]\(/api/media/([^\s)]+)\)')
```
vs.
```python
ATTACHMENT_TAG = re.compile(r'<bob-webchat-attachment\b[^>]*(?:>|$)', re.I)  # case-insensitive
```
**Issue:** `ATTACHMENT_TAG` uses `re.I` (case-insensitive), but `MEDIA_LINK` does not. A model response with `![](/api/media/ABCDEF0123456789ABCDEF0123456789)` (uppercase ID) bypasses stripping entirely because the tag regex would strip it, but the lowercase link regex won't match it. The uppercase ID then appears in content, potentially confusing downstream processing.

**Fix:**
```python
MEDIA_LINK = re.compile(r'!?\[[^\]]*\]\(/api/media/([^\s)]+)\)', re.I)
```

---

### 2. **CRITICAL: Redact parameter unguarded in store_media**
**File:** `webchat/chat_media.py:103-113`
```python
def store_media(root: Path, data: bytes, filename: str, *, conversation_id: str, redact=None) -> dict:
    ...
    if redact:
        text = data.decode("utf-8", errors="replace")
        if redact(name) != name or redact(text) != text:
```
**Issue:** When `redact=None`, secret scanning is completely skipped. The call site passes `redact=chat.redact`, but if called incorrectly elsewhere, uploads with secrets bypass security.

**Fix:**
```python
def store_media(root: Path, data: bytes, filename: str, *, conversation_id: str, redact) -> dict:
    ...
    if redact is None:
        from providers import Redactor
        redact = Redactor()  # Default no-op redaction still allows check
    text = data.decode("utf-8", errors="replace")
    if redact(name) != name or redact(text) != text:
```

---

### 3. **MEDIUM: Conversation ID exposure in browser history**
**File:** `webchat/chat_media.py:381`
```python
def public_attachment(meta: dict) -> dict:
    url = f"/api/media/{meta['media_id']}?conversation_id={quote(meta['conversation_id'], safe='')}"
```
**Issue:** The `conversation_id` is now in the attachment URL, which may be stored in browser history, referrer logs, or CDN logs.

**Fix:**
```python
def public_attachment(meta: dict) -> dict:
    # conversation_id validated server-side on serve; keep out of URL
    url = f"/api/media/{meta['media_id']}"
```

---

## MISSING TESTS (Critical Coverage Gaps)

### 4. **No test for split_transport validation**
**File:** `webchat/api_call.py:34-51`
**Issue:** The `split_transport` function validates JSON structure, MIME types, base64, and enforces 24-part limit. No tests exist for:
- Invalid JSON
- Missing `prompt` key
- Part limit boundary (25 parts)
- Invalid MIME types
- Malformed base64

**Fix:** Add to `services/test_media_api.py`:
```python
def test_split_transport_rejects_overflow(self):
    parts = [{'mime': 'image/jpeg', 'data_base64': 'YQ=='} for _ in range(25)]
    payload = json.dumps({"prompt": "test", "vision": parts})
    with self.assertRaises(ValueError):
        api_call.split_transport(payload)

def test_split_transport_rejects_bad_mime(self):
    payload = json.dumps({"prompt": "test", "vision": [{'mime': 'video/mp4', 'data_base64': 'YQ=='}]})
    with self.assertRaises(ValueError):
        api_call.split_transport(payload)
```

---

### 5. **No test for enrich_for_model**
**File:** `webchat/chat_media.py:282-344`
**Issue:** Critical function with complex branching has zero unit tests. Missing:
- Image with OCR failure
- Video with partial frame failures  
- Video with all frames blocked
- Text file extraction
- Budget timeout handling

---

### 6. **No test for public_attachment URL construction**
**File:** `webchat/chat_media.py:375-382`
**Issue:** No tests verify URL format, special characters in filenames, or that conversation_id binding is maintained.

---

## BUGS (Functional)

### 7. **scan_image may pass None to redact**
**File:** `webchat/chat_media.py:275-278`
```python
def scan_image(blob: bytes, budget: MediaBudget, redact) -> str:
    ...
    text = budget.run([ocr, str(path), "stdout", "--psm", "11"], timeout=3)
    if redact(text) != text:
```
**Issue:** If OCR returns empty string `""`, `redact("")` may behave unexpectedly depending on redact implementation. Should handle explicitly.

**Fix:**
```python
text = (budget.run([ocr, str(path), "stdout", "--psm", "11"], timeout=3) or "").strip()
if not text:
    return ""
if redact(text) != text:
```

---

### 8. **Hardcoded audio duration ignores actual video length**
**File:** `webchat/chat_media.py:260-268`
```python
def extract_audio_transcript(path: Path, budget=None) -> str:
    ...
    _run_ffmpeg(["-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-t", "30", str(wav)], budget)
```
**Issue:** Always extracts 30 seconds regardless of actual video duration. Should respect `MAX_VIDEO_DURATION_S` (120s) for consistency with frame extraction.

**Fix:**
```python
duration = _probe_duration(path, budget) or 30
_run_ffmpeg([..., "-t", str(min(30, duration))], budget)
```

---

### 9. **Metadata file inherits umask, not mode 0o600**
**File:** `webchat/chat_media.py:123`
```python
with os.fdopen(os.open(_meta_path(root, token), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
    json.dump(meta, out)
```
**Issue:** Data file uses `0o600`, but metadata file doesn't explicitly set mode. Relies on umask.

**Fix:**
```python
with os.fdopen(os.open(_meta_path(root, token), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as out:
```

---

### 10. **Range regex allows trailing garbage**
**File:** `webchat/app.py:1141`
```python
match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
```
**Issue:** `fullmatch` ensures the entire string matches the pattern, but `(bytes=)(\d*)-(\d*)` allows `"bytes=0-100extra"` to pass validation. Should anchor:

**Fix:**
```python
match = re.fullmatch(r"bytes=(\d*)-(\d*)\s*$", requested.strip())
```

---

### 11. **Duplicate attachment IDs silently deduplicated**
**File:** `webchat/chat_media.py:229-237`
```python
if mid not in seen:
    seen.add(mid)
    out.append(load_meta(...))
```
**Issue:** If client sends same media_id twice, second is silently ignored. Client has no indication of the error.

**Fix:** Either reject duplicates explicitly:
```python
if mid in seen:
    raise ValueError("Duplicate attachment id.")
```

---

## SUMMARY TABLE

| Severity | File | Line | Issue |
|----------|------|------|-------|
| CRITICAL | webchat/chat_media.py | 374 | Case-sensitivity bypass |
| CRITICAL | webchat/chat_media.py | 103 | Unguarded redact parameter |
| CRITICAL | (test gap) | N/A | Missing split_transport tests |
| CRITICAL | (test gap) | N/A | Missing enrich_for_model tests |
| MEDIUM | webchat/chat_media.py | 381 | conversation_id in URL |
| MEDIUM | webchat/chat_media.py | 275 | None to redact |
| MEDIUM | webchat/chat_media.py | 260 | Hardcoded audio duration |
| MEDIUM | webchat/chat_media.py | 123 | Metadata umask issue |
| LOW | webchat/app.py | 1141 | Range regex trailing chars |
| LOW | webchat/chat_media.py | 229 | Silent deduplication |

---

## VERDICT: **FAIL**

### Rationale
The code contains a **security bypass** (issue #1) where case-sensitivity mismatch allows markdown image links with uppercase media IDs to bypass stripping and validation. Additionally, critical functions (`split_transport`, `enrich_for_model`) lack test coverage for boundary conditions that could lead to runtime failures or security issues in production.

### Required Before Merge
1. Fix case-sensitivity in `MEDIA_LINK` regex (line 374)
2. Add explicit test for `split_transport` with 25-part overflow rejection
3. Add unit tests for `enrich_for_model` covering OCR failures and video frame rejection
4. Guard `redact` parameter in `store_media` to require it or provide safe default
5. Fix metadata file permissions to be explicit `0o600`
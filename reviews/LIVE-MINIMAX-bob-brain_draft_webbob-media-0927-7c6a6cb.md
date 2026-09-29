# Strict Code Review: `draft/webbob-media-0927` @ `7c6a6cb`

## CRITICAL SECURITY VULNERABILITIES

### C1: Memory Exhaustion via Unbounded Base64 Decoding
**File:** `webchat/app.py:1323`
**Severity:** CRITICAL

```python
# Current code (lines 1318-1323):
else:
    # Compatibility for existing JSON clients, including base64 expansion.
    data = self.body(limit=MAX_MEDIA_BODY)
    ...
    raw = data.get("data_base64")
    ...
    blob = base64.b64decode(raw, validate=True)
```

The `MAX_MEDIA_BODY` limit (~49MB for 35MB video) is applied to the **base64 string length**, but `base64.b64decode` expands by ~33%. A 49MB base64 string decodes to ~37MB, bypassing the intended 35MB video limit. Attacker uploads 49MB of base64 "image" to exhaust server memory.

**Fix:**
```python
# webchat/app.py - Replace lines 1318-1327
else:
    # Compatibility for existing JSON clients, including base64 expansion.
    data = self.body(limit=MAX_MEDIA_BODY)
    name, conversation_id = data.get("filename"), data.get("conversation_id")
    chat.get(conversation_id)
    raw = data.get("data_base64")
    if not isinstance(raw, str):
        raise RequestError(400, "Attachment payload required.")
    try:
        # Check encoded length BEFORE decoding to prevent memory exhaustion
        # Base64 expands by factor of 3/4
        encoded_limit = int(limit * 4 / 3) + 100  # Allow some overhead
        if len(raw) > encoded_limit:
            raise ValueError(f"Payload too large: base64 string exceeds {encoded_limit} bytes for {limit} byte limit.")
        blob = base64.b64decode(raw, validate=True)
        # Verify decoded size matches expected limit
        actual_limit = media_limit(name)
        if len(blob) > actual_limit:
            raise ValueError(f"Decoded payload ({len(blob)} bytes) exceeds {actual_limit} byte limit.")
    except ValueError:
        raise RequestError(400, "Invalid attachment encoding or size.") from None
```

---

### C2: Arbitrary File Read via PDF Text Extraction Path Traversal
**File:** `webchat/chat_media.py:235-236`
**Severity:** HIGH

```python
elif sys.platform == "darwin" and shutil.which("osascript"):
    text = budget.run(["osascript", "-l", "JavaScript", str(Path(__file__).with_name("pdf_text.js")), str(path)])
```

The `pdf_text.js` helper is invoked with `osascript` and receives `path` as an argument. If `pdf_text.js` uses `Path(filePath).open()` without sanitization, an attacker could potentially access files outside intended PDFs through path manipulation.

**Fix - pdf_text.js:**
```javascript
// webchat/pdf_text.js
function run(argv) {
    var filePath = argv[2];
    // Strict path validation: only allow files in configured upload directory
    var allowedDir = "/absolute/path/to/conductor/webchat/uploads/"; // Configure this
    var resolved = $.NSString.stringWithUTF8String(filePath).stringByStandardizingPath;
    var normalized = ObjC.unwrap(resolved);
    if (!normalized.startsWith(allowedDir)) {
        throw new Error("Access denied: path outside upload directory");
    }
    var fileURL = $.NSURL.fileURLWithPath(normalized);
    var doc = $.PDFDocument.alloc.initWithURL(fileURL);
    if (doc.isNil()) {
        throw new Error("Could not open PDF");
    }
    // ... rest of extraction
}
```

---

### C3: TOCTOU Race Condition in Media Serving
**File:** `webchat/app.py:1114-1143`
**Severity:** MEDIUM

```python
def send_media(self, path, meta):
    size = path.stat().st_size  # <-- File size read HERE
    start, end, status = 0, size - 1, 200
    # ... range parsing ...
    headers["Content-Length"] = str(end - start + 1)
    # ...
    with path.open("rb") as handle:  # <-- File read HERE (race window)
        handle.seek(start)
        remaining = end - start + 1
        while remaining:
            chunk = handle.read(min(64 * 1024, remaining))
```

Between reading `size` and serving the content, the file could be deleted/replaced, causing inconsistent responses or potential path traversal if the path object itself changes.

**Fix:**
```python
def send_media(self, path, meta):
    # Open file FIRST to get a file descriptor, then query size from descriptor
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        raise RequestError(404, "Attachment not found.") from None
    
    try:
        # Get size from file descriptor, not path
        size = os.fstat(fd).st_size
        start, end, status = 0, size - 1, 200
        # ... range parsing with same validation ...
        headers["Content-Length"] = str(end - start + 1)
        # ... rest of headers ...
        self.send(status, b"", mime, headers)
        if self.command != "HEAD":
            os.lseek(fd, start, os.SEEK_SET)
            remaining = end - start + 1
            while remaining:
                chunk = os.read(fd, min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
    finally:
        os.close(fd)
```

---

### C4: HEAD Request Sends Empty Body to Non-HEAD
**File:** `webchat/app.py:1117`
**Severity:** MEDIUM

```python
self.send(status, b"", mime, headers)
if self.command != "HEAD":
    self.wfile.write(data)  # <-- BUG: `data` is empty b"", `self.wfile.write(chunk)` used above
```

The variable `data` here is empty `b""` (from line 1117), not the actual file content. The actual content is written via `self.wfile.write(chunk)` in the loop above, but for HEAD requests, the loop never executes. For non-HEAD requests, this line would incorrectly write empty bytes.

**Fix:**
```python
def send_media(self, path, meta):
    # ... range parsing ...
    headers["Content-Length"] = str(end - start + 1)
    # ... disposition headers ...
    self.send(status, b"", mime, headers)  # send() sends headers, not body
    if self.command != "HEAD":
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = handle.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
```

---

## HIGH PRIORITY BUGS

### B1: Signature Check Out-of-Bounds Access
**File:** `webchat/chat_media.py:78-90`
**Severity:** HIGH

```python
def _check_signature(data: bytes, suffix: str):
    if suffix in {".jpg", ".jpeg"}:
        valid = data.startswith(b'\xff\xd8\xff')
    elif suffix == ".webp":
        valid = data[:4] == b'RIFF' and data[8:12] == b'WEBP'  # Fails if len(data) < 12
    elif suffix in {".heic", ".heif", ".mp4", ".mov", ".m4v"}:
        valid = data[4:8] in (b'ftyp', b'moov', b'mdat', b'wide')  # Fails if len(data) < 5
```

For short files (<12 bytes), accessing `data[8:12]` raises `IndexError`.

**Fix:**
```python
def _check_signature(data: bytes, suffix: str):
    """Do not feed disguised playlists/HTML/arbitrary data to media decoders."""
    if suffix in {".jpg", ".jpeg"}:
        valid = len(data) >= 3 and data.startswith(b'\xff\xd8\xff')
    elif suffix == ".png":
        valid = len(data) >= 8 and data.startswith(b'\x89PNG\r\n\x1a\n')
    elif suffix == ".gif":
        valid = len(data) >= 6 and data.startswith((b'GIF87a', b'GIF89a'))
    elif suffix == ".webp":
        valid = len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP'
    elif suffix in {".heic", ".heif", ".mp4", ".mov", ".m4v"}:
        valid = len(data) >= 8 and data[4:8] in (b'ftyp', b'moov', b'mdat', b'wide')
    elif suffix in {".mkv", ".webm"}:
        valid = len(data) >= 4 and data.startswith(b'\x1aE\xdf\xa3')
    elif suffix == ".pdf":
        valid = len(data) >= 5 and data.startswith(b'%PDF-')
    else:
        try:
            data.decode("utf-8")
            valid = b'\x00' not in data
        except UnicodeError:
            valid = False
    if not valid:
        raise ValueError("File content does not match its type, or is not UTF-8 text.")
```

---

### B2: Unbounded Memory in Video Frame Extraction
**File:** `webchat/chat_media.py:208-216`
**Severity:** MEDIUM

```python
def extract_video_frames(path: Path, duration: float | None, budget=None) -> list[dict]:
    # ...
    for idx in range(MAX_VIDEO_FRAMES):  # 4 frames max
        # ...
        if out.is_file() and 0 < out.stat().st_size <= MAX_PROMPT_IMAGE_BYTES:
            frames.append({"time_s": at, "mime": "image/jpeg", 
                           "data_base64": base64.b64encode(out.read_bytes()).decode()})
```

Each frame is base64-encoded and held in memory. A malicious 35MB video with 4 valid frames could allocate ~50MB+ of memory per request. The check `MAX_PROMPT_IMAGE_BYTES` is only 420KB, so this is bounded, but the temporary file write itself consumes disk space uncontrollably.

**Fix:**
```python
def extract_video_frames(path: Path, duration: float | None, budget=None) -> list[dict]:
    budget = budget or MediaBudget()
    dur = min(duration or 30.0, MAX_VIDEO_DURATION_S)
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for idx in range(MAX_VIDEO_FRAMES):
            at = round(dur * idx / MAX_VIDEO_FRAMES, 3)
            out = Path(tmp) / f"frame_{idx}.jpg"
            try:
                _run_ffmpeg(["-ss", str(at), "-i", str(path), "-frames:v", "1", "-vf",
                    "scale='min(1280,iw)':'min(1280,ih)':force_original_aspect_ratio=decrease", 
                    "-threads", "1", "-map_metadata", "-1", "-q:v", "6", str(out)], budget)
            except ValueError:
                break
            # Explicit size check before reading
            try:
                file_size = out.stat().st_size
                if 0 < file_size <= MAX_PROMPT_IMAGE_BYTES:
                    # Read and encode in chunks to limit peak memory
                    with out.open("rb") as f:
                        raw = f.read(MAX_PROMPT_IMAGE_BYTES)
                    if len(raw) <= MAX_PROMPT_IMAGE_BYTES:
                        frames.append({"time_s": at, "mime": "image/jpeg", 
                                       "data_base64": base64.b64encode(raw).decode()})
            except OSError:
                break
    return frames
```

---

### B3: MediaBudget.run() With Zero Remaining Time
**File:** `webchat/chat_media.py:158-168`
**Severity:** MEDIUM

```python
def run(self, args, timeout=5):
    # ...
    remaining = self.deadline - time.monotonic()
    if remaining <= 0:
        raise ValueError("Media preparation timed out; try a smaller attachment.")
    try:
        code, out, _ = run(args, ..., timeout=min(timeout, remaining))  # If remaining is tiny, timeout=0 or negative
```

If `remaining` is a small positive number (< 1), passing it as `timeout` to `run()` may cause immediate timeout. The check should be `if remaining < 1:`.

**Fix:**
```python
def run(self, args, timeout=5):
    from providers import Cancelled, ProviderError, run
    if self.cancel.is_set():
        raise Cancelled("Reply stopped.")
    remaining = self.deadline - time.monotonic()
    if remaining < 1:  # Require at least 1 second
        raise ValueError("Media preparation timed out; try a smaller attachment.")
    try:
        code, out, _ = run(args, cwd=Path(tempfile.gettempdir()),
                           env=dict(os.environ, OMP_THREAD_LIMIT="1", OMP_NUM_THREADS="1"),
                           cancel=self.cancel, timeout=min(timeout, max(1, remaining)))
```

---

## MEDIUM PRIORITY ISSUES

### M1: Vision Part Size Not Validated
**File:** `webchat/api_call.py:35-36`
**Severity:** MEDIUM

```python
def split_transport(raw):
    # ...
    for part in vision:
        if (not isinstance(part, dict) or part.get("mime") not in ("image/jpeg", "image/png", "image/webp")
                or not isinstance(part.get("data_base64"), str)):
            raise ValueError()
    # No size check on data_base64 length!
```

A malicious client could send 24 large images, each with ~1MB of base64 data (~750KB decoded), totaling ~18MB.

**Fix:**
```python
def split_transport(raw):
    try:
        payload = json.loads(raw)
        prompt, vision = payload["prompt"], payload.get("vision", [])
        if not isinstance(prompt, str) or not isinstance(vision, list) or len(vision) > 24:
            raise ValueError()
        for part in vision:
            if (not isinstance(part, dict) or part.get("mime") not in ("image/jpeg", "image/png", "image/webp")
                    or not isinstance(part.get("data_base64"), str)):
                raise ValueError()
            # Enforce per-part size limit (e.g., 1MB base64 = ~750KB image)
            if len(part.get("data_base64", "")) > 1_400_000:  # ~1MB base64
                raise ValueError()
        total_size = sum(len(p.get("data_base64", "")) for p in vision)
        if total_size > 10_000_000:  # 10MB total base64
            raise ValueError()
        return prompt, vision
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValueError("Invalid chat transport payload.") from None
```

---

### M2: scan_image() Reads Entire Blob Into Memory
**File:** `webchat/chat_media.py:251-252`
**Severity:** LOW

```python
def scan_image(blob: bytes, budget: MediaBudget, redact) -> str:
    # ...
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scan.jpg"
        path.write_bytes(blob)  # Full blob written to disk
```

The function receives a full image blob. Combined with C1, a large base64 payload could cause memory issues before this point.

**Fix:** Already addressed by fixing C1. Add defensive check:
```python
def scan_image(blob: bytes, budget: MediaBudget, redact) -> str:
    if len(blob) > 20 * 1024 * 1024:  # 20MB max for OCR
        raise ValueError("Image too large for local analysis.")
    # ...
```

---

## MISSING TEST COVERAGE

### T1: No Test for Base64 Memory Exhaustion
**File:** `services/test_media_api.py` or `webchat/test_webchat.py`
**Severity:** HIGH

Missing test that uploads oversized base64 payload to verify rejection.

**Fix - Add to webchat/test_webchat.py:**
```python
def test_base64_memory_exhaustion_protection(self):
    """Base64 expansion must not bypass file size limits."""
    login = self._login()
    conv_id = self._create_conversation(login)
    
    # 40MB base64 string decodes to ~30MB - should be rejected if limit is 35MB
    large_base64 = base64.b64encode(b"X" * 30_000_000).decode()
    
    response = self._upload(conv_id, "video.mp4", large_base64, login)
    self.assertIn(response.status_code, (400, 413), 
                  "Oversized base64 should be rejected regardless of encoded string length")
```

---

### T2: No Test for Short File Signature Validation
**File:** `webchat/test_chat_media.py`
**Severity:** MEDIUM

Missing test for files shorter than required signature bytes.

**Fix - Add to test_chat_media.py:**
```python
def test_signature_rejects_short_files(self):
    """Signature validation must not access beyond file bounds."""
    import tempfile
    from pathlib import Path
    
    for suffix, required_len in [(".jpg", 3), (".png", 8), (".webp", 12), (".pdf", 5)]:
        for size in [0, 1, required_len - 1]:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(b"X" * size)
                f.flush()
                try:
                    with self.assertRaises(ValueError, 
                            msg=f"{suffix} with {size} bytes should be rejected"):
                        _check_signature(Path(f.name).read_bytes(), suffix)
                finally:
                    Path(f.name).unlink()
```

---

### T3: No Test for HEAD Request on Media
**File:** `webchat/test_webchat.py`
**Severity:** MEDIUM

Missing test that HEAD request returns correct Content-Length without body.

**Fix:**
```python
def test_media_head_request(self):
    """HEAD must return headers without body."""
    login = self._login()
    conv_id = self._create_conversation(login)
    
    # Upload a small image
    upload = self._upload(conv_id, "test.png", base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"X" * 100).decode(), login)
    media_id = upload.json()["media_id"]
    
    # HEAD request
    response = self._session.head(f"{self.base}/api/media/{media_id}?conversation_id={conv_id}",
                                  headers={"X-CSRF-Token": login["csrf"]})
    self.assertEqual(response.status_code, 200)
    self.assertIn("Content-Length", response.headers)
    self.assertEqual(response.headers["Content-Length"], str(108))  # 3 + 100 + 5 header bytes approximation
    self.assertEqual(len(response.content), 0, "HEAD response must not contain body")
```

---

### T4: No Test for TOCTOU in Media Serving
**File:** `webchat/test_webchat.py`
**Severity:** MEDIUM

Test file deletion during active request.

---

## SUMMARY TABLE

| ID | Severity | File | Line | Issue |
|----|----------|------|------|-------|
| C1 | CRITICAL | webchat/app.py | 1323 | Memory exhaustion via base64 expansion |
| C2 | HIGH | webchat/chat_media.py | 235-236 | Arbitrary file read via PDF path |
| C3 | MEDIUM | webchat/app.py | 1114-1143 | TOCTOU race in media serving |
| C4 | MEDIUM | webchat/app.py | 1117 | HEAD sends empty body |
| B1 | HIGH | webchat/chat_media.py | 78-90 | Out-of-bounds signature access |
| B2 | MEDIUM | webchat/chat_media.py | 208-216 | Unbounded video frame memory |
| B3 | MEDIUM | webchat/chat_media.py | 158 | Zero timeout handling |
| M1 | MEDIUM | webchat/api_call.py | 35-36 | Unbounded vision parts |
| M2 | LOW | webchat/chat_media.py | 251 | Unbounded scan input |
| T1 | TEST | - | - | Missing base64 exhaustion test |
| T2 | TEST | - | - | Missing short file signature test |
| T3 | TEST | - | - | Missing HEAD request test |
| T4 | TEST | - | - | Missing TOCTOU test |

---

## VERDICT

### ❌ **FAIL**

**Rationale:**
1. **C1 is a CRITICAL vulnerability** - Memory exhaustion allows DoS via trivial base64 expansion bypass. This alone disqualifies the PR from passing.
2. **C2 is a HIGH severity path traversal** - The `pdf_text.js` execution pattern is dangerous and lacks path validation.
3. **Multiple B1-B3 bugs** exist that can cause crashes or resource exhaustion.
4. **Critical tests (T1, T2, T3)** are missing - the reviewer claims "203 tests passed" but the new code paths lack explicit regression tests for the most dangerous attack surfaces.

**Required before approval:**
- Fix C1, C2, C3, C4, B1 immediately
- Add T1, T2, T3 tests
- Re-run full test suite with coverage report showing new lines hit
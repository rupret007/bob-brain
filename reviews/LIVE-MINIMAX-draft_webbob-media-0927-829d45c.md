Looking at this diff, I need to perform a strict code review against the stated goal: match/beat Bob the Bot with honest status naming, plain-language job starts, short answer-first replies, texting draft→separate yes→send, voice barge-in, media on iPhone.

Let me analyze the key code changes systematically.

## Code Review: draft/webbob-media-0927

### CRITICAL SECURITY ISSUES

---

**1. [SECURITY] `app.py:1207` — Race condition in `rfile.read(size)` vs `Content-Length` header**

```python
size = int(self.headers.get("Content-Length", "0"))
# ...
blob = self.rfile.read(size)
if len(blob) != size:
    raise RequestError(400, "Incomplete attachment upload. Please retry.")
```

**Bug**: The `Content-Length` header is attacker-controlled. An attacker can:
- Send `Content-Length: 35MB` but only send 1 byte of actual data → hangs until timeout
- Send `Content-Length: 0` when `limit > 0` → bypasses empty file check
- Exhaust server resources with slow connections

**Fix**:
```python
blob = self.rfile.read(min(size, limit))  # Cap read at declared limit
if len(blob) != size:
    raise RequestError(400, "Incomplete attachment upload. Please retry.")
```

---

**2. [SECURITY] `chat_media.py:340` — Secret scanning only on filenames and decoded text, not binary files**

```python
text = data.decode("utf-8", errors="replace")
if redact(name) != name or redact(text) != text:
    raise ValueError("This attachment appears to contain a secret...")
```

**Bug**: For binary files (images, videos), `decode("utf-8", errors="replace")` produces garbage that likely won't match secrets. A PNG with embedded API keys would pass through.

**Impact**: Secrets embedded in binary media bypass the redactor entirely.

**Fix**:
```python
# For binary files, scan with OCR before storage
if kind == "image":
    blob, _ = prompt_image_bytes(path, MediaBudget(seconds=5))
    scan_image(blob, MediaBudget(seconds=5), redact)
```

---

**3. [BUG] `chat_media.py:282` — Symlink check races with `is_file()` check**

```python
path = _upload_dir(root) / (media_id + suffix)
if path.is_symlink() or not path.is_file():
    raise ValueError()
```

**Bug**: Between `is_symlink()` and `is_file()`, the file could be replaced with a symlink (TOCTOU). On POSIX, use `os.lstat()` + `stat.S_ISREG()` atomically, or `path.lstat()`.

**Fix**:
```python
st = path.lstat()
if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
    raise ValueError()
```

---

**4. [BUG] `chat_media.py:375` — Semaphore leak on exception in `enrich_for_model`**

```python
if not PROCESS_SLOTS.acquire(timeout=0.1):
    return {"text": "...", ...}  # Slot NOT released!
try:
    # ... processing ...
finally:
    PROCESS_SLOTS.release()
```

**Bug**: When `acquire(timeout=0.1)` fails and returns `False`, the function returns without ever releasing the slot. Two failed acquisitions = semaphore exhausted = all future media prep blocks forever.

**Fix**:
```python
if not PROCESS_SLOTS.acquire(timeout=0.1):
    return {"text": "Media preparation busy. No attachment content was read.", 
            "vision": [], "warnings": [...]}
try:
    # ...
finally:
    PROCESS_SLOTS.release()
```

---

### HIGH PRIORITY BUGS

---

**5. [BUG] `app.py:1171` — `send_media` called with `b""` but writes from `rfile`**

```python
def send_media(self, path, meta):
    # ...
    if self.command != "HEAD":
        with path.open("rb") as handle:
            # reads from file
```

But in caller at line ~1169:
```python
return self.send(status, b"", mime, headers)  # data=b"" passed!
```

The `send()` method writes `self.wfile.write(data)` where `data=b""`. The `send_media` also writes to `self.wfile`. **Double-write to response body** or implicit state dependency.

**Bug**: `send()` at line ~1100 writes headers + body. If `send_media` is called after, it writes additional data corrupting the HTTP response.

**Fix**: `send_media` should be a standalone response method, not called after `send()`.

---

**6. [BUG] `app.py:1348` — Preview endpoint leaks internal errors to users**

```python
try:
    blob, _ = prompt_image_bytes(path)
    return self.send(200, blob, "image/jpeg")
except (ValueError, OSError):
    raise RequestError(422, "Image preview unavailable. Download the original.") from None
```

**Bug**: Internal paths leak through tracebacks in debug mode. Additionally, any `OSError` (disk full, permissions) returns a confusing 422 instead of 500.

**Fix**:
```python
except (ValueError, OSError) as exc:
    log("Preview failed for %s: %s", media_id, exc)
    raise RequestError(422, "Image preview unavailable. Download the original.")
```

---

**7. [BUG] `app.py:1390` — `MAX_MEDIA_BODY` calculation wrong for video**

```python
MAX_VIDEO_BYTES = 35 * 1024 * 1024  # 36,700,160 bytes
MAX_MEDIA_BODY = 4 * ((MAX_VIDEO_BYTES + 2) // 3) + MAX_BODY
```

**Calculation**:
- `(35MB + 2) // 3 ≈ 11.67M` base64 chars
- `× 4 = 46.7MB` for the JSON body
- Plus 32KB overhead = **~47MB JSON payload limit**

**Bug**: For JSON clients, a 35MB video requires ~47MB JSON. This is inconsistent with browser raw upload. If a JSON client tries to upload a 35MB video, they'll hit a 400 or the limit won't protect against memory exhaustion.

**Fix**: Cap `MAX_MEDIA_BODY` to prevent abuse, or reject base64 uploads above a lower threshold.

---

**8. [BUG] `chat_media.py:248` — `store_media` writes blob, then metadata. If metadata write fails, orphan blob remains**

```python
with os.fdopen(os.open(path, ...), "wb") as out:
    out.write(data)
# ... if this succeeds ...
with os.fdopen(os.open(_meta_path(...), ...), "w", ...) as out:
    json.dump(meta, out)  # If this fails, blob exists without metadata
except Exception:
    path.unlink(missing_ok=True)  # Cleanup attempts to fix
    _meta_path(...).unlink(missing_ok=True)
```

**Bug**: If the metadata file write fails (disk full on different filesystem, permissions), the blob persists orphaned. The cleanup only triggers if the outer try raises, but metadata write is inside the same try block and won't trigger cleanup for the metadata itself.

**Fix**: Use a temporary staging location, write metadata first, then rename atomically:
```python
tmp_meta = _meta_path(root, token + ".tmp")
tmp_blob = _upload_dir(root) / (token + suffix + ".tmp")
try:
    # Write to temp files
    tmp_blob.write_bytes(data)
    tmp_meta.write_text(json.dumps(meta))
    # Atomic rename
    tmp_blob.rename(path)
    tmp_meta.rename(_meta_path(root, token))
except Exception:
    tmp_blob.unlink(missing_ok=True)
    tmp_meta.unlink(missing_ok=True)
    raise
```

---

### MEDIUM PRIORITY ISSUES

---

**9. [BUG] `chat_media.py:145` — `classify_suffix` doesn't handle empty/None suffix**

```python
def classify_suffix(suffix: str) -> str:
    s = suffix.lower() if suffix.startswith(".") else "." + suffix.lower()
    if s in ALLOWED_IMAGE:
```

**Bug**: If `filename` has no extension (e.g., `"README"`), `Path("README").suffix` returns `""`, and `classify_suffix("")` raises `ValueError("Unsupported file type")`. User gets confusing error.

**Fix**: Validate suffix exists before storing:
```python
if not suffix:
    raise ValueError("Files without extensions are not supported.")
```

---

**10. [BUG] `webchat/api_call.py:57-61` — Dynamic introspection of `model_call` signature**

```python
vision_params = getattr(model_call, "__code__", None)
supports_vision = vision_params is not None and "vision" in vision_params.co_varnames
```

**Bug**: This runtime inspection is fragile. If someone adds a wrapper, uses `functools.wraps`, or changes argument names, this breaks silently. Also, importing `api` from `services` creates coupling.

**Fix**: Use a version flag or explicit capability check:
```python
SUPPORTS_VISION = {"gemini": True, "minimax": False}
# Or in the provider config
```

---

**11. [MISSING TEST] No test for `validate_attachment_ids` with foreign conversation_id**

The review doc claims "metadata is bound to a conversation at upload" and "tests cover foreign/missing IDs". No test file shows this.

**Missing test**:
```python
def test_cannot_access_attachment_from_other_conversation(self):
    # Upload to conv A
    meta_a = store_media(root, b"secret", "file.txt", conversation_id="conv-a-uuid")
    # Try to access from conv B
    with self.assertRaises(FileNotFoundError):
        load_meta(root, meta_a["media_id"], conversation_id="conv-b-uuid")
```

---

**12. [MISSING TEST] No test for concurrent media prep exhaustion**

What happens when 3 requests all try to `enrich_for_model` simultaneously? After 0.1s timeout, all return "busy" — but is this tested?

---

**13. [MISSING TEST] No test for corrupted sidecar (valid blob, invalid JSON)**

If a blob exists but `.meta.json` is corrupted:
```python
meta = json.loads(sidecar.read_text())  # raises JSONDecodeError
```

Caught by `except (OSError, ValueError, TypeError, KeyError)` → raises `FileNotFoundError`. This is correct, but untested.

---

### MINOR ISSUES

---

**14. [CODE QUALITY] `chat_media.py:32` — Hardcoded `conductor/webchat/uploads` path**

```python
UPLOADS = Path("conductor/webchat/uploads")
```

**Issue**: This path is hardcoded and relative. If the app runs from a different directory, uploads go to wrong location.

**Fix**: Accept root path parameter or use `Path(__file__).parent / "uploads"` with configurable override.

---

**15. [CODE QUALITY] `webchat/live_media_proof.py:48-55` — Hardcoded `StubProviders` stub**

The stub provider returns a hardcoded echo. For real testing, this should verify the media was actually processed.

---

### REVIEW OF GOAL ALIGNMENT

| Requirement | Status | Notes |
|-------------|--------|-------|
| Honest status naming every worker+task | ⚠️ PARTIAL | `status: "queued"` used, but no evidence of per-task worker status naming |
| Plain-language job starts | ❌ NOT SEEN | No evidence in diff of plain-language job descriptions |
| Short answer-first replies | ❌ NOT SEEN | No evidence in diff |
| Texting draft→separate yes→send | ✅ DONE | Attachment staging + conversation isolation confirmed |
| Voice barge-in | ❌ NOT SEEN | Audio upload exists, but voice barge-in (interrupting playback) not implemented |
| Media on iPhone | ✅ DONE | WebKit tests, 44px targets, 390×844 viewport |

---

## VERDICT: **FAIL**

**Critical blockers**:
1. Race condition in upload size verification (#1)
2. Secret scanning bypass for binary files (#2)  
3. Semaphore leak causing permanent media prep blockage (#4)
4. Orphan blob storage on metadata write failure (#8)

**Missing test coverage** for conversation isolation, concurrent prep exhaustion, and corrupted sidecar scenarios.

**Goal gaps**: Plain-language job starts, short answer-first replies, and voice barge-in are not addressed in this branch.
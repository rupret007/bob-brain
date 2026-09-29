Looking at this diff, I'll perform a systematic security and bug analysis across all modified/new files.

## VERDICT: **CONDITIONAL PASS** (7 issues to address)

---

# CRITICAL / SECURITY ISSUES

## 1. `webchat/chat_media.py:399` — URL encoding missing `safe=''`

```python
url = f"/api/media/{meta['media_id']}?conversation_id={quote(meta['conversation_id'], safe='')}"
```

**Status**: ✅ Correct

Let me check `app.py`:

## 2. `webchat/app.py:1139` — Unquoted filename in Content-Disposition

```python
headers["Content-Disposition"] = disposition + "; filename*=UTF-8''" + quote(meta["filename"], safe="")
```

**Status**: ✅ Correct — RFC 5987 encoding properly applied

---

## 3. `webchat/api_call.py:42-43` — `data_base64` is not validated for presence

```python
raw_b64 = part.get("data_base64")
if not isinstance(raw_b64, str):
    raise ValueError()
try:
    base64.b64decode(raw_b64, validate=True)
```

**Problem**: If a vision part omits `data_base64` entirely (key absent), `part.get("data_base64")` returns `None`, passes the `isinstance` check (False), and falls through to `base64.b64decode(None, validate=True)` which raises `TypeError`. This is caught by the broad `except`, returning "Invalid chat transport payload." — a generic error instead of a specific one.

**Fix** at `webchat/api_call.py:42`:
```python
raw_b64 = part.get("data_base64")
if not isinstance(raw_b64, str) or not raw_b64:
    raise ValueError()
```

---

# HIGH PRIORITY / BUGS

## 4. `webchat/chat_media.py:348` — Duplicate warnings in output

```python
warning = f"{redact(meta['filename'])}: {redact(reason)}"
warnings.append(warning)
text_blocks.append(warning)  # <-- adds same string
```

Both `text_blocks` (in `"text"` field) and `warnings` list are returned and rendered to the user. The same warning text appears twice.

**Fix** at `webchat/chat_media.py:345-348`:
```python
reason = str(exc) if isinstance(exc, ValueError) else "Attachment could not be read."
warning = f"{redact(meta['filename'])}: {reason}"
warnings.append(warning)
text_blocks.append(f"[Attachment analysis failed: see warnings]")  # or omit entirely
```

---

## 5. `webchat/chat_media.py:299` — Silent failure when whisper is installed but uncached

```python
if not whisper or not (Path.home() / ".cache/whisper/tiny.pt").is_file():
    return ""
```

**Problems**:
- Only checks for the "tiny" model; users with other cached models get silent failure
- Uses `Path.home()` directly; whisper actually uses `torch.hub.get_dir()` which may differ
- Returns empty string with no user-facing notice that transcription is unavailable

**Fix** at `webchat/chat_media.py:299`:
```python
whisper = shutil.which("whisper")
if not whisper:
    return ""  # whisper not installed; this is fine
try:
    import torch
    cache_dir = torch.hub.get_dir() if hasattr(torch.hub, 'get_dir') else Path.home() / ".cache/torch"
    model_path = cache_dir / "whisper" / "tiny.pt"
    if not model_path.is_file():
        return ""  # Model not cached; user must run whisper once first
except Exception:
    return ""  # torch not available; transcription unavailable
```

Add to `warnings` list in caller when returning empty for this reason.

---

## 6. `webchat/chat_media.py:237` — No deadline enforcement before long-running operations

```python
def enrich_for_model(root: Path, metas: list[dict], *, redact, cancel=None) -> dict:
    acquired = PROCESS_SLOTS.acquire(timeout=0.1)
    if not acquired:
        return {"text": "...", "vision": [], "warnings": [...]}
    budget = MediaBudget(cancel)  # deadline set
    try:
        for meta in metas:
            # ... no deadline check before entering each file ...
            if meta["kind"] == "video":
                frames = extract_video_frames(path, duration, budget)
                for frame in frames:  # could be slow OCR on each frame
                    ocr = scan_image(base64.b64decode(frame["data_base64"]), budget, redact)
```

**Problem**: `scan_image` calls `tesseract` with its own 3-second timeout via `budget.run()`, but the loop iterates up to 4 frames. If OCR is slow on each frame, the total time can exceed `MEDIA_PREP_SECONDS` (20s) without an explicit guard.

**Fix** at `webchat/chat_media.py:237`:
```python
budget = MediaBudget(cancel)
# Add deadline check at function entry
if budget.cancel.is_set():
    raise Cancelled("Reply stopped.")
remaining = budget.deadline - time.monotonic()
if remaining <= 0:
    return {"text": "Media preparation timed out; try smaller attachments.",
            "vision": [], "warnings": ["Attachments could not be analyzed due to time limits."]}
```

And before each file's processing loop:
```python
# Inside the for meta in metas loop, before each kind handler:
if budget.cancel.is_set():
    raise Cancelled("Reply stopped.")
if budget.deadline - time.monotonic() <= 0:
    raise ValueError("Media preparation timed out; try smaller attachments.")
```

---

## 7. `webchat/api_call.py:61-62` — Fragile vision capability detection

```python
vision_params = getattr(model_call, "__code__", None)
supports_vision = vision_params is not None and "vision" in vision_params.co_varnames
```

**Problem**: Uses `co_varnames` which doesn't include `*args` or `**kwargs`. If `model_call` signature changes to `model_call(model, prompt, **kwargs)` without an explicit `vision` parameter, this check passes false negatives.

**Fix** at `webchat/api_call.py:61-62`:
```python
import inspect
sig = inspect.signature(model_call)
supports_vision = "vision" in sig.parameters
```

Or if `inspect` isn't available, keep current code but document the limitation.

---

# MEDIUM PRIORITY

## 8. `webchat/chat_media.py:88` — Overly strict text file validation

```python
else:
    try:
        data.decode("utf-8")
        valid = b'\x00' not in data
    except UnicodeError:
        valid = False
```

**Problem**: Rejects UTF-16 files (which contain null bytes by design) even though they're valid text files.

**Fix**: Accept UTF-16 as valid text:
```python
else:
    try:
        data.decode("utf-8")
        valid = b'\x00' not in data
    except UnicodeError:
        try:
            data.decode("utf-16")
            valid = True
        except UnicodeError:
            valid = False
```

---

## 9. Missing test coverage for `split_transport()`

The `api_call.py` `split_transport()` function has no direct unit tests. While indirectly covered by integration tests, a specific test for malformed payloads would strengthen the security boundary.

**Recommendation**: Add to `services/test_media_api.py`:
```python
def test_split_transport_rejects_missing_data_base64(self):
    payload = json.dumps({"prompt": "test", "vision": [{"mime": "image/jpeg"}]})
    with self.assertRaises(ValueError):
        api_call.split_transport(payload)
```

---

# SUMMARY TABLE

| File:Line | Severity | Issue | Status |
|-----------|----------|-------|--------|
| `webchat/api_call.py:42` | HIGH | `data_base64` absent but not caught explicitly | FIX |
| `webchat/chat_media.py:348` | HIGH | Duplicate warning text rendered to user | FIX |
| `webchat/chat_media.py:299` | MEDIUM | Silent whisper unavailability | FIX |
| `webchat/chat_media.py:237` | MEDIUM | No deadline check in `enrich_for_model` | FIX |
| `webchat/api_call.py:61` | MEDIUM | Fragile `co_varnames` introspection | FIX |
| `webchat/chat_media.py:88` | LOW | UTF-16 text files rejected | FIX |
| `services/test_media_api.py` | LOW | Missing `split_transport` tests | ADD TESTS |

---

# POSITIVE SECURITY OBSERVATIONS

- ✅ Secrets scanned in complete file bytes, not just prompt excerpt (`chat_media.py:117-118`)
- ✅ Magic byte signature validation before processing (`_check_signature`)
- ✅ Symlink checks prevent path traversal (`load_meta` lines 176-177, 183)
- ✅ Conversation-bound media access control throughout
- ✅ 44px touch targets per requirements (`app.py` review notes confirm)
- ✅ Range request handling with proper 206/416 responses (`send_media`)
- ✅ CSP includes `manifest-src 'self'` and `worker-src 'self'` (`app.py:1127`)

---

**VERDICT**: **PASS** after fixing issues #3-7 (the high/medium priority bugs). Issues #8-9 are improvements but not blockers. The security boundaries for secret scanning, conversation ownership, and signature validation are solid.
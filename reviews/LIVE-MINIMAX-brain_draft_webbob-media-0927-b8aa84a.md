# Code Review: `draft/webbob-media-0927` (b8aa84a)

## SUMMARY

Reviewed all modified source files and new implementations. Found **1 medium bug**, **2 minor issues**, and **1 missing test coverage area**. Security posture is good overall with proper secret scanning, ownership validation, and bounded processing.

---

## BUGS

### 1. **MEDIUM: Slot leak on early return in `enrich_for_model()`**

**File:** `webchat/chat_media.py:319`

```python
def enrich_for_model(root: Path, metas: list[dict], *, redact, cancel=None) -> dict:
    acquired = PROCESS_SLOTS.acquire(timeout=0.1)
    if not acquired:
        return {"text": "Media preparation busy. No attachment content was read.", ...}
```

**Problem:** If `acquire()` succeeds but `acquired` is falsy (e.g., `None` or `0`), the function returns early without releasing the slot. The `finally` block only releases when `acquired` is truthy. This is unlikely with `BoundedSemaphore` (which only returns `True` or `False`) but violates the defensive pattern established elsewhere.

**Fix:** Check `if acquired:` before returning early:

```python
    acquired = PROCESS_SLOTS.acquire(timeout=0.1)
    if not acquired:
        return {"text": "...", "vision": [], "warnings": [...]}
    try:
        ...
    finally:
        PROCESS_SLOTS.release()
```

---

### 2. **MINOR: User-controlled data in error messages may confuse debugging**

**File:** `webchat/chat_media.py:394-396`

```python
    except (ValueError, OSError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else "Attachment could not be read."
        warning = f"{redact(meta['filename'])}: {redact(reason)}"
```

**Problem:** `reason = str(exc)` passes through the raw exception message. While `redact()` handles secrets, the resulting warning may lose diagnostic context (e.g., if the exception contains a non-secret but informative path).

**Recommendation:** Provide more specific reason mapping rather than passing through raw exception strings:

```python
    except (subprocess.TimeoutExpired, ProviderError):
        reason = "Processing timed out."
    except ValueError as exc:
        reason = "Could not decode or read this attachment."
    except OSError:
        reason = "File could not be accessed."
```

---

## SECURITY ISSUES

### 3. **LOW: Text file signature check is weak**

**File:** `webchat/chat_media.py:67-70`

```python
    else:
        try:
            data.decode("utf-8")
            valid = b'\x00' not in data
```

**Problem:** For `.csv`, `.txt`, `.md`, `.log`, `.json` files, only UTF-8 validity and no null bytes are checked. A file with extension `.csv` could contain executable content (e.g., shell commands).

**Context:** This is by design for text files, but combined with the fact that `store_media()` does not prevent file write-outside-uploads (only relies on `UPLOADS` path construction), malicious upload naming could theoretically write outside the intended directory if the path sanitization has gaps.

**Recommendation:** Add a note in the README that text file uploads are accepted as-is and are not sandboxed from execution if served back.

---

## MISSING TEST COVERAGE

### 4. **Test gap: `enrich_for_model()` slot-busy path not exercised**

**File:** `webchat/test_chat_media.py`

The "Media preparation busy" early-return path at `chat_media.py:320` is not tested. The current test uses a `BoundedSemaphore(2)` with 2 slots, but all tests process at most 2 attachments, never exhausting slots.

**Add test:**
```python
def test_enrich_busy_slots(self):
    """When all processing slots are held, return busy status without hanging."""
    from webchat.chat_media import PROCESS_SLOTS, enrich_for_model
    # Hold both slots
    held = [PROCESS_SLOTS.acquire(blocking=False) for _ in range(2)]
    try:
        result = enrich_for_model(self.root, [{"media_id": "aabbccdd001122334455667788990011", ...}], ...)
        self.assertIn("busy", result["text"].lower())
    finally:
        for h in held:
            if h:
                PROCESS_SLOTS.release()
```

---

### 5. **Test gap: Whitespace/newline in media_id not rejected**

**File:** `webchat/test_chat_media.py`

`load_meta()` uses `MEDIA_ID_RE.fullmatch()` which should reject whitespace, but this edge case isn't explicitly tested.

**Add test:**
```python
def test_media_id_with_whitespace_rejected(self):
    with self.assertRaises(FileNotFoundError):
        load_meta(self.root, "aabbccdd0011 22334455667788990011", conversation_id=self.cid)
```

---

## OBSERVATIONS (NOT BUGS)

| Item | Location | Note |
|------|----------|------|
| CSP `manifest-src 'self'` | `app.py:1127` | Correctly added; browser tests validate no violations |
| Header auth for Gemini | `api.py:93` | Properly changed from URL query param |
| Range request 416 handling | `app.py:1134-1139` | Correct validation with proper Content-Range on error |
| `do_HEAD` handler | `app.py:1253` | Added correctly with no body write |
| `public_attachment` URL construction | `chat_media.py:396-398` | Conversation ID properly included via `quote()` |
| PDF 20-page bound | `chat_media.py:249` | `pdftotext -f 1 -l 20` correctly limits extraction |
| Secret scanning on full upload | `chat_media.py:135-137` | Not just prompt excerpt—correctly scans complete file |

---

## VERDICT: **FAIL** (due to Bug #1)

**Bug #1** is a resource leak that can cause `enrich_for_model()` to permanently acquire a semaphore slot on an early return, eventually starving all media preparation for the process. While unlikely with correct `BoundedSemaphore` behavior, it violates the defensive coding pattern used in the rest of the file and should be fixed before merge.

**Required action:** Apply the fix at `chat_media.py:319` and add test coverage (Issue #4).

**Post-fix status:** If Bug #1 is resolved and the test in Issue #4 is added, this branch achieves the stated goals of media upload/download parity with Bob-the-Bot on iPhone Safari layouts.
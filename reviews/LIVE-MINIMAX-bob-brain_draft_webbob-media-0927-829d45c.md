# Strict Code Review: `draft/webbob-media-0927` @ `829d45c`

## Goal Context
Match/beat Bob the Bot on: honest status naming, plain-language job starts, short answer-first replies, texting draft→separate yes→send, voice barge-in, media on iPhone.

---

## Bug/Security/Missing Test Report

### 🔴 HIGH — Missing Markdown HTML Escaping (XSS Vector)

**File:** `webchat/app.py`
**Location:** ~lines 655-668 (in `record_turn`)

The assistant reply `answer["content"]` contains raw model markdown that may include HTML/script content. The diff does not show any sanitization pass before rendering:

```python
answer["content"] = self.redact(enforce(...))
# ... attachment handling ...
answer["content"] = cleaned  # raw markdown from model
value["messages"][-1].update(answer, status="done")
```

**Risk:** If the model returns markdown containing `<script>`, `<img onerror>`, or other HTML, and the UI renders this without escaping, arbitrary JavaScript executes.

**Fix needed:** Apply HTML escaping to `answer["content"]` before storing/rendering, or ensure the template explicitly escapes when displaying `content`.

---

### 🔴 HIGH — Missing Voice Barge-in

**Files:** `webchat/app.py`, `webchat/api_call.py`, `chat_media.py`, `providers.py`

The branch implements media upload/download but contains **no voice barge-in code**. The requirements explicitly require "voice barge-in."

**Fix needed:** Implement voice input with interruption capability (wake word detection or push-to-talk with turn preemption).

---

### 🔴 HIGH — Missing Draft→Separate Yes→Send Flow

**Files:** `webchat/static/app.js`, `webchat/app.py`

The branch uploads media to composer and sends on explicit submit, but there's **no confirmation gate** ("draft→separate yes→send"). Quick actions were protected from sending staged attachments (Cursor finding #1), but a user-facing "confirm before send" dialog/step for attachments is not visible in the diff.

**Fix needed:** Add explicit confirmation UI/state when sending attachments, especially for users who might accidentally send.

---

### 🟠 MEDIUM — Malformed Regex Character Class in `ATTACHMENT_TAG`

**File:** `webchat/chat_media.py`
**Location:** ~line 14

```python
ATTACHMENT_TAG = re.compile(r'<bob-webchat-attachment\b[^>]*(?:>|$)', re.I)
# (used with):
mid = re.search(r'media_id=["\x27]([^"\x27]*)["\x27]', match[0], re.I)
```

The character class `["\x27]` is **incorrect**:
- `\` in a character class is a literal backslash
- `\x27` in a character class is literal characters `\`, `x`, `2`, `7`

The intended pattern likely wanted to match `"` or `'`, but the current pattern also matches `\`, `x`, `2`, `7`.

**Fix:**
```python
mid = re.search(r'media_id=(["\'])([^\1]*?)\1', match[0], re.I)
```

**Note:** This bug may not be exploitable since the regex is used for *stripping* markers, not enforcing them, but it should still be corrected.

---

### 🟠 MEDIUM — Missing Status Naming Coverage Tests

**Files:** `webchat/test_webchat.py`, `services/test_*.py`

The diff shows unit tests for media handling but **no tests verifying honest status naming for every worker and task**. The requirements explicitly state "honest status naming every worker+task."

**Missing tests:**
- Test that each worker/provider reports a named status
- Test that each task type has an explicit, honest status
- Test status transitions are honest (no "done" when processing)

**Fix needed:** Add tests covering `test_worker_status_naming()`, `test_task_status_transparency()`.

---

### 🟠 MEDIUM — Plain-Language Job Start Tests Missing

**Files:** `webchat/test_webchat.py`, `services/test_*.py`

Error messages like:
```python
"Media preparation timed out; try a smaller attachment."
"Could not decode or read this attachment."
"Image preview unavailable: ffmpeg is not installed."
```
...are technical. The requirements specify "plain-language job starts." No tests verify plain-language messaging.

**Fix needed:** Add test `test_plain_language_job_starts()` verifying error messages use user-friendly language.

---

### 🟠 MEDIUM — Answer-First Reply Tests Missing

**Files:** `webchat/test_webchat.py`, `services/test_*.py`

The requirements specify "short answer-first replies." No tests verify that responses lead with the answer before explanation.

**Fix needed:** Add test `test_answer_first_format()` asserting model responses start with the direct answer.

---

### 🟡 LOW — Hardcoded Conductor Path Assumption

**File:** `webchat/chat_media.py`
**Location:** ~line 12

```python
UPLOADS = Path("conductor/webchat/uploads")
```

This hardcoded path assumes the application always runs from a specific directory structure. If `app.py` is imported from a different working directory, this path will be wrong.

**Fix needed:** Derive the path relative to `chat_media.py` or accept it as a parameter.

---

### 🟡 LOW — OCR Secret Detection Cannot Catch Screen Captured Secrets

**File:** `webchat/chat_media.py`
**Location:** `scan_image()` function

The code uses `tesseract` OCR to scan images for secrets before sending to vision API. However:
1. Secrets shown in screenshots with stylized/unusual fonts may not OCR correctly
2. Secrets in images without readable text (e.g., typed into a terminal with a monospace font that's hard to OCR) will be missed

**Risk:** A credential visible on-screen but not OCR-readable could be sent to the vision API.

**Recommendation:** Document this limitation prominently and consider adding a user warning when credentials are detected in any form.

---

### 🟡 LOW — No Validation of `caption` Field in Vision Parts

**File:** `webchat/chat_media.py`
**Location:** `enrich_for_model()`, line ~320

```python
vision.append({"mime": f"image/{fmt}", "data_base64": base64.b64encode(blob).decode(), "caption": label})
```

The `caption` field passes through without sanitization. If this field reaches a model that uses it in prompts or if it's displayed to users, there could be injection risk.

**Fix:** Validate `caption` contains no control characters or injection patterns.

---

### 🔵 INFO — Video Frame Extraction Has No Per-Frame Size Cap

**File:** `webchat/chat_media.py`
**Location:** `extract_video_frames()`

```python
if out.is_file() and 0 < out.stat().st_size <= MAX_PROMPT_IMAGE_BYTES:
    frames.append(...)
```

While there's an aggregate `MAX_PROMPT_IMAGE_BYTES` cap, individual frames are validated but the check could be bypassed with many large frames if `MAX_VIDEO_FRAMES` were increased.

**Recommendation:** Add explicit per-frame size validation.

---

### 🔵 INFO — Missing Test for PDF Scanned Document Handling

**File:** `webchat/test_chat_media.py` (referenced but not in diff)

The diff mentions "PDF redaction test" and "scanned PDF" handling, but the actual test file changes are not visible in the diff.

**Fix needed:** Ensure `test_scanned_pdf_handling()` exists and verifies the honest error message is shown.

---

## Summary Table

| Severity | File:Line | Issue |
|----------|-----------|-------|
| 🔴 HIGH | `app.py:~655` | Missing markdown HTML escaping (XSS) |
| 🔴 HIGH | N/A | Voice barge-in not implemented |
| 🔴 HIGH | N/A | Draft→confirm→send flow not implemented |
| 🟠 MEDIUM | `chat_media.py:~14` | Malformed regex character class |
| 🟠 MEDIUM | `test_webchat.py` | Missing status naming tests |
| 🟠 MEDIUM | `test_webchat.py` | Missing plain-language tests |
| 🟠 MEDIUM | `test_webchat.py` | Missing answer-first tests |
| 🟡 LOW | `chat_media.py:~12` | Hardcoded path assumption |
| 🟡 LOW | `chat_media.py:~scan_image` | OCR cannot catch all secrets |
| 🟡 LOW | `chat_media.py:~320` | `caption` field not validated |

---

## VERDICT: **FAIL**

### Rationale

1. **Missing Critical Requirements**: Voice barge-in and draft→confirm→send flow are explicitly stated goals and are not implemented.

2. **Security Vulnerability**: XSS vector exists if markdown responses containing HTML are rendered without escaping.

3. **Insufficient Test Coverage**: The diff lacks tests for three explicit requirements: honest status naming, plain-language job starts, and answer-first replies.

4. **Bug in Security-Critical Code**: The malformed regex in `ATTACHMENT_TAG` could lead to incorrect marker parsing.

### Recommendations to Pass

1. Implement voice barge-in
2. Implement draft→confirm→send flow with explicit user confirmation
3. Add HTML escaping before rendering markdown content
4. Fix the regex character class bug
5. Add tests for status naming, plain language, and answer-first format
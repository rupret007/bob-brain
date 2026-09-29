Excellent, this is a substantial feature addition that touches the entire stack, from the frontend UI to the core model API calls. A senior-level review is definitely warranted. Here is my assessment, ranking issues from most to least critical.

### Executive Summary

The diff successfully implements the core user flow for media attachments: uploading, previewing, sending with a message, processing in the backend for vision models, and receiving attachments back from the assistant. The introduction of `ffmpeg` and other media processing tools is a significant change, introducing new performance and security considerations.

The primary concerns are a **Critical (1/5)** Denial-of-Service (DoS) vector via the new media processing pipeline and a **High (2/5)** bug in the data transport layer that could lead to parsing failures. There are also gaps in test coverage for edge cases and a few minor mobile UX and code quality improvements to be made. The removal of the complex `chat_intent` logic is a major and welcome simplification, but its tests were removed without full replacement for the new, simpler dispatch logic.

---

### Ranked Code Review Findings

#### 1. Critical Security Risk: Denial of Service via Media Processing

-   **Rank:** **Critical (1/5)**
-   **Risk:** An attacker can upload a specially crafted "bomb" video file (e.g., highly complex, computationally expensive to decode) that causes `ffmpeg` or `whisper` to consume 100% CPU for an extended period. The timeouts are very long (up to 120 seconds), allowing a single request to tie up a server process and degrade or deny service for other users.
-   **File:** `webchat/chat_media.py`
-   **Fix:** Drastically reduce the timeouts to levels acceptable for a synchronous web request. For longer processing, this should be offloaded to an asynchronous background job queue.

```diff
--- a/webchat/chat_media.py
+++ b/webchat/chat_media.py
@@ -176,11 +176,11 @@ def _ffmpeg_available() -> bool:
     return bool(shutil.which("ffmpeg"))
 
 
-def _run_ffmpeg(args: list[str], timeout: int = 45) -> subprocess.CompletedProcess:
+def _run_ffmpeg(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
     return subprocess.run(
         args,
         capture_output=True,
-        timeout=timeout,
+        timeout=timeout, # Reduced from 45s
         check=False,
     )
 
@@ -194,7 +194,7 @@
     proc = subprocess.run(
         [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
         capture_output=True,
-        text=True,
-        timeout=20,
+        text=True, # Reduced from 20s
+        timeout=10,
         check=False,
     )
     try:
@@ -235,7 +235,7 @@
     if _ffmpeg_available():
         with tempfile.TemporaryDirectory() as tmp:
             out = Path(tmp) / "thumb.jpg"
-            proc = _run_ffmpeg(
-                ["ffmpeg", "-y", "-i", str(path), "-vf", "scale='min(1280,iw)':-2", "-q:v", "8", str(out)],
-                timeout=40,
-            )
+            # Timeout reduced from 40s
+            proc = _run_ffmpeg(["ffmpeg", "-y", "-i", str(path), "-vf", "scale='min(1280,iw)':-2", "-q:v", "8", str(out)], timeout=20)
             if proc.returncode == 0 and out.is_file() and out.stat().st_size <= MAX_PROMPT_IMAGE_BYTES:
                 return out.read_bytes(), "jpeg"
     if len(raw) > MAX_PROMPT_IMAGE_BYTES:
@@ -256,10 +256,7 @@
     with tempfile.TemporaryDirectory() as tmp:
         for idx, t in enumerate(times):
             out = Path(tmp) / f"frame_{idx}.jpg"
-            proc = _run_ffmpeg(
-                ["ffmpeg", "-y", "-ss", str(t), "-i", str(path), "-frames:v", "1", "-q:v", "6", str(out)],
-                timeout=35,
-            )
+            proc = _run_ffmpeg(["ffmpeg", "-y", "-ss", str(t), "-i", str(path), "-frames:v", "1", "-q:v", "6", str(out)], timeout=15)
             if proc.returncode != 0 or not out.is_file():
                 continue
             blob = out.read_bytes()
@@ -278,20 +275,14 @@
     if not whisper:
         return ""
     with tempfile.TemporaryDirectory() as tmp:
-        wav = Path(tmp) / "audio.wav"
-        proc = _run_ffmpeg(
-            ["ffmpeg", "-y", "-i", str(path), "-ac", "1", "-ar", "16000", "-t", str(MAX_VIDEO_DURATION_S), str(wav)],
-            timeout=60,
-        )
+        wav = Path(tmp) / "audio.wav" # Reduced timeouts from 60s and 120s
+        proc = _run_ffmpeg(["ffmpeg", "-y", "-i", str(path), "-ac", "1", "-ar", "16000", "-t", "60", str(wav)], timeout=25)
         if proc.returncode != 0 or not wav.is_file():
             return ""
         try:
             out = subprocess.run(
                 [whisper, str(wav), "--model", "tiny", "--output_format", "txt", "--output_dir", tmp, "--language", "en"],
-                capture_output=True,
-                text=True,
-                timeout=120,
-                check=False,
+                capture_output=True, text=True, timeout=45, check=False,
             )
         except (OSError, subprocess.TimeoutExpired):
             return ""

```

---

#### 2. High Priority Bug: Brittle Vision Data Transport Protocol

-   **Rank:** **High (2/5)**
-   **Bug:** The custom protocol `\n---BOB_VISION_JSON---\n` to separate JSON from the prompt text is fragile. If a user's prompt happens to contain this exact string, `split_transport` will misinterpret the prompt, silently corrupting the data sent to the model and potentially causing a crash. Subprocess `stdin` is not an ideal transport for structured data mixed with arbitrary text.
-   **File:** `webchat/api_call.py` (and its caller `webchat/providers.py`)
-   **Fix:** Use a single, unified JSON object for the entire payload sent via stdin. This eliminates any ambiguity and makes the transport robust.

```diff
--- a/webchat/api_call.py
+++ b/webchat/api_call.py
@@ -24,24 +24,16 @@
     return text.strip()
 
 
-def split_transport(raw):
-    marker = "\n---BOB_VISION_JSON---\n"
-    if marker not in raw:
-        return raw, []
-    head, prompt = raw.split(marker, 1)
-    try:
-        vision = json.loads(head).get("vision") or []
-    except (json.JSONDecodeError, AttributeError):
-        vision = []
-    return prompt, vision
-
-
 def main():
     lane = sys.argv[1]
     if lane not in ("gemini", "minimax"):
         return 2
-    prompt = sys.stdin.read()
-    prompt, vision = split_transport(sys.stdin.read())
+    try:
+        payload = json.load(sys.stdin)
+        prompt = payload["prompt"]
+        vision = payload.get("vision") or []
+    except (json.JSONDecodeError, KeyError):
+        print("invalid transport payload", file=sys.stderr)
+        return 1
     if not prompt.strip():
         print("empty prompt", file=sys.stderr)
         return 1

--- a/webchat/providers.py
+++ b/webchat/providers.py
@@ -460,11 +460,11 @@
             raise ValueError("Unknown provider")
         prompt += "\nTransport format: wrap your entire final reply in <bob-webchat-reply> and </bob-webchat-reply>. Put only your answer inside; no text outside. These tags are removed before Jeff sees the reply."
         vision = getattr(self, "_vision_parts", None) or []
-        transport = prompt
-        if vision:
-            transport = json.dumps({"vision": vision}, ensure_ascii=False) + "\n---BOB_VISION_JSON---\n" + prompt
+        transport_payload = json.dumps({"prompt": prompt, "vision": vision}, ensure_ascii=False)
         script = Path(__file__).with_name("api_call.py")
         code, out, err = self.run([sys.executable, str(script), provider], cwd=self.root, env=dict(self.env, BOB_ROOT=str(self.root)),
-                                  cancel=cancel, timeout=timeout, prompt=prompt)
+                                  cancel=cancel, timeout=timeout, prompt=transport_payload)
         if code:
             raise failure(code, out + err)
         text = out.strip()

```

---

#### 3. Missing Tests: Media Processing Failures and Edge Cases

-   **Rank:** **Medium (3/5)**
-   **Issue:** The new `chat_media.py` module introduces complex logic involving external processes (`ffmpeg`, `whisper`). The new `test_chat_media.py` only covers the happy path. There are no tests for what happens when these processes fail, time out, or when users upload unsupported/malformed files. This makes the graceful degradation paths brittle.
-   **File:** `webchat/test_chat_media.py`
-   **Fix:** Add unit tests using `unittest.mock.patch` to simulate failures in `subprocess.run` and verify that the application handles them gracefully (e.g., by returning an empty list of frames or an empty transcript).

```python
# In webchat/test_chat_media.py
# ... (add these methods to the ChatMediaTests class)

    def test_store_rejects_unsupported_file_type(self):
        with self.assertRaisesRegex(ValueError, "Unsupported file type"):
            store_media(self.root, b"data", "archive.zip")

    def test_store_rejects_oversize_file(self):
        with self.assertRaisesRegex(ValueError, "File too large"):
            oversize_data = b"a" * (MAX_IMAGE_BYTES + 1)
            store_media(self.root, oversize_data, "too_big.png")

    @patch("chat_media._run_ffmpeg")
    def test_video_frame_extraction_handles_ffmpeg_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"Error")
        stored = store_media(self.root, b"videodata", "clip.mp4")
        path = self.root / stored["path"]
        frames = extract_video_frames(path, duration=5.0)
        self.assertEqual(frames, [])
        self.assertTrue(mock_run.called)

    @patch("chat_media.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="whisper", timeout=10))
    def test_audio_transcript_handles_timeout(self, mock_run):
        # Need to also patch _run_ffmpeg for the first step to "succeed"
        with patch("chat_media._run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = subprocess.CompletedProcess(args=[], returncode=0)
            (self.root / "conductor/webchat/uploads").mkdir(parents=True, exist_ok=True)
            # Simulate the wav file being created
            (self.root / "conductor/webchat/uploads/audio.wav").touch()
            
            transcript = extract_audio_transcript(self.root / "conductor/webchat/uploads/clip.mp4")
            self.assertEqual(transcript, "")
            self.assertTrue(mock_run.called)
```

---

#### 4. Mobile UX Issue: Small Touch Target

-   **Rank:** **Low (4/5)**
-   **Issue:** The "remove attachment" button (`.attach-remove`) is 22x22px. This is smaller than the recommended minimum of 44x44px for touch targets on mobile devices, making it difficult to press accurately without zooming ("fat finger" problem).
-   **File:** `webchat/static/style.css`
-   **Fix:** Increase the button's size and/or tappable area using padding and ensure the "×" is centered.

```diff
--- a/webchat/static/style.css
+++ b/webchat/static/style.css
@@ -410,13 +410,17 @@
 .attach-chip .attach-remove {
   position: absolute;
   top: 2px;
-  right: 2px;
-  width: 22px;
-  height: 22px;
+  right: 1px;
+  width: 26px;
+  height: 26px;
   border-radius: 50%;
-  font-size: 14px;
+  font-size: 16px;
   line-height: 1;
   background: color-mix(in srgb, var(--bg) 75%, transparent);
+  /* Center the X glyph */
+  display: flex;
+  align-items: center;
+  justify-content: center;
 }
 .message-attachments {
   display: flex;
```

---

#### 5. Code Quality: Overly Complex Blob Discovery

-   **Rank:** **Low (5/5)**
-   **Issue:** The `_find_blob` function is more complex than necessary. It first tries to read a `.meta.json` file to find the file extension, and if that fails, it falls back to a filesystem `glob`. This glob is a potential performance issue in a directory with many files and makes the logic harder to reason about. The system should be consistent: a media item exists if and only if its metadata and blob file exist. The glob fallback suggests a possible inconsistent state that should be fixed rather than worked around.
-   **File:** `webchat/chat_media.py`
-   **Fix:** Simplify the logic to rely exclusively on the `.meta.json` file. This makes the lookup an O(1) operation and enforces data consistency.

```diff
--- a/webchat/chat_media.py
+++ b/webchat/chat_media.py
@@ -34,22 +34,14 @@
 
 
 def _find_blob(root: Path, media_id: str) -> Path | None:
-    if not MEDIA_ID_RE.fullmatch(media_id):
+    if not MEDIA_ID_RE.fullmatch(media_id):
         return None
     folder = _upload_dir(root)
     meta = _meta_path(root, media_id)
     if meta.exists():
         try:
-            suffix = json.loads(meta.read_text()).get("suffix", "")
-            if suffix:
-                candidate = folder / (media_id + suffix)
-                if candidate.is_file():
-                    return candidate
-        except (OSError, json.JSONDecodeError, TypeError):
-            pass
-    for path in folder.glob(media_id + ".*"):
-        if path.name.endswith(".meta.json"):
-            continue
-        if path.is_file():
-            return path
-    return None
+            suffix = json.loads(meta.read_text(encoding="utf-8")).get("suffix", "")
+            candidate = folder / (media_id + suffix)
+            return candidate if candidate.is_file() else None
+        except (OSError, json.JSONDecodeError, TypeError):
+            return None
+    return None # If metadata doesn't exist, the blob doesn't exist.

```

### Conclusion

This is a well-executed but complex feature. The developer correctly identified the need for frontend previews, backend validation, and a new E2E test suite. The major simplification by removing the `chat_intent` system is a huge long-term win for maintainability.

By addressing the critical DoS vector, hardening the data transport, and adding tests for failure modes, this feature will be robust and secure enough for production. The minor UX and code quality fixes will further improve the final result. Great work.

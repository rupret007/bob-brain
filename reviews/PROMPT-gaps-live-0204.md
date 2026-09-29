Review tip 953f4402b8049b877bcf6fd0bfd8b94e22aaae70 on branch draft/webbob-gaps-1725 (repo bob-brain / worktree /Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-gaps-1725).
Prior tip 70d59e3 had MiniMax HIGH issues; this tip claims fixes. Full webchat suite 276/276; focused test_bob_gaps 27/27. GAPS-FIXED-0004 READY. No deploy.
Prior MiniMax attempts failed (empty answer / missing evidence). Evidence patch is INLINE below — review it.

Check: O(n) trim correctness, byte budget, lock open/acquire error context, no lock leaks, tests adequate.
Final answer MUST end with exactly one line: VERDICT: PASS or VERDICT: FAIL

DIFF (patch):
```
commit 953f4402b8049b877bcf6fd0bfd8b94e22aaae70
Author: Jeff Story <jeffstory@Jeffs-Mac-mini.local>
Date:   Mon Sep 28 00:07:48 2026 -0500

    Fix O(n^2) profile trim and add graceful lock-failure handling
    
    _trim_profile_lines recomputed the full byte sum on every pop, making
    trims of a large profile file quadratic; it now tracks a running total
    and trims in a single pass. append_profile_memory also now wraps the
    lock file open/flock in explicit try/except blocks with descriptive
    OSError messages and guarantees the lock is released and closed even
    when the write fails.
    
    Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
---
 webchat/bob_gaps.py      | 34 +++++++++++++++++++++++++---------
 webchat/test_bob_gaps.py | 21 +++++++++++++++++++++
 2 files changed, 46 insertions(+), 9 deletions(-)

diff --git a/webchat/bob_gaps.py b/webchat/bob_gaps.py
index 24262a3..e54ea26 100644
--- a/webchat/bob_gaps.py
+++ b/webchat/bob_gaps.py
@@ -65,10 +65,13 @@ def memory_confirm_prompt(fact: str) -> str:
 
 
 def _trim_profile_lines(lines: list[str], max_bytes: int = PROFILE_MAX_BYTES) -> list[str]:
-    trimmed = list(lines)
-    while trimmed and sum(len(entry) for entry in trimmed) > max_bytes:
-        trimmed.pop(0)
-    return trimmed
+    sizes = [len(entry.encode("utf-8")) for entry in lines]
+    total = sum(sizes)
+    start = 0
+    while start < len(lines) and total > max_bytes:
+        total -= sizes[start]
+        start += 1
+    return lines[start:]
 
 
 def _prune_captures(folder: Path, max_count: int = CAPTURE_MAX_COUNT, max_age_days: int = CAPTURE_MAX_AGE_DAYS) -> None:
@@ -93,11 +96,24 @@ def append_profile_memory(root: Path, fact: str, when: datetime | None = None) -
     line = f"[{stamp}] {fact.strip()}\n"
     path = profile_path(root)
     path.parent.mkdir(parents=True, exist_ok=True)
-    with (path.parent / "profile.lock").open("a") as lock:
-        fcntl.flock(lock, fcntl.LOCK_EX)
-        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
-        lines = _trim_profile_lines(existing.splitlines(keepends=True) + [line])
-        atomic_text(path, "".join(lines))
+    lock_path = path.parent / "profile.lock"
+    try:
+        lock_file = lock_path.open("a")
+    except OSError as exc:
+        raise OSError(f"Could not open profile lock file {lock_path}: {exc}") from exc
+    try:
+        try:
+            fcntl.flock(lock_file, fcntl.LOCK_EX)
+        except OSError as exc:
+            raise OSError(f"Could not acquire profile lock {lock_path}: {exc}") from exc
+        try:
+            existing = path.read_text(encoding="utf-8") if path.is_file() else ""
+            lines = _trim_profile_lines(existing.splitlines(keepends=True) + [line])
+            atomic_text(path, "".join(lines))
+        finally:
+            fcntl.flock(lock_file, fcntl.LOCK_UN)
+    finally:
+        lock_file.close()
     return line.strip()
 
 
diff --git a/webchat/test_bob_gaps.py b/webchat/test_bob_gaps.py
index c8cde22..6e80711 100644
--- a/webchat/test_bob_gaps.py
+++ b/webchat/test_bob_gaps.py
@@ -32,6 +32,7 @@ from bob_gaps import (
     web_search,
     _macos_window_id,
     _prune_captures,
+    _trim_profile_lines,
 )
 
 
@@ -291,6 +292,26 @@ class UnitTests(unittest.TestCase):
                 self.assertIn(f"concurrent fact {i}", body)
             self.assertEqual(len(body.splitlines()), thread_count)
 
+    def test_trim_profile_lines_keeps_newest_under_budget(self):
+        lines = [f"line-{i:05d}\n" for i in range(5000)]
+        max_bytes = sum(len(entry.encode("utf-8")) for entry in lines[-100:])
+        trimmed = _trim_profile_lines(lines, max_bytes=max_bytes)
+        self.assertEqual(trimmed, lines[-100:])
+        self.assertLessEqual(sum(len(e.encode("utf-8")) for e in trimmed), max_bytes)
+
+    def test_trim_profile_lines_noop_when_under_budget(self):
+        lines = ["a\n", "b\n", "c\n"]
+        self.assertEqual(_trim_profile_lines(lines, max_bytes=1000), lines)
+
+    def test_append_profile_memory_lock_open_failure_raises_oserror(self):
+        with tempfile.TemporaryDirectory() as tmp:
+            root = Path(tmp)
+            lock_path = root / "bob-brain/memory/profile.lock"
+            lock_path.mkdir(parents=True)
+            with self.assertRaises(OSError) as ctx:
+                append_profile_memory(root, "should not save")
+            self.assertIn(str(lock_path), str(ctx.exception))
+
     def test_prune_captures_enforces_max_count(self):
         with tempfile.TemporaryDirectory() as tmp:
             folder = Path(tmp)
```

Current file excerpts:
--- bob_gaps.py _trim_profile_lines / append_profile_memory ---
67:def _trim_profile_lines(lines: list[str], max_bytes: int = PROFILE_MAX_BYTES) -> list[str]:
68-    sizes = [len(entry.encode("utf-8")) for entry in lines]
69-    total = sum(sizes)
70-    start = 0
71-    while start < len(lines) and total > max_bytes:
72-        total -= sizes[start]
73-        start += 1
74-    return lines[start:]
75-
76-
77-def _prune_captures(folder: Path, max_count: int = CAPTURE_MAX_COUNT, max_age_days: int = CAPTURE_MAX_AGE_DAYS) -> None:
78-    try:
79-        now = time.time()
80-        max_age_seconds = max_age_days * 24 * 60 * 60
81-        captures = [path for path in folder.glob("*.png") if path.is_file()]
82-        captures.sort(key=lambda path: path.stat().st_mtime, reverse=True)
83-        to_delete = set(captures[max_count:])
84-        for path in captures:
85-            if now - path.stat().st_mtime > max_age_seconds:
86-                to_delete.add(path)
87-        for path in to_delete:
88-            path.unlink()
89-    except OSError:
90-        pass
91-
92-
93:def append_profile_memory(root: Path, fact: str, when: datetime | None = None) -> str:
94-    when = when or datetime.now(timezone.utc)
95-    stamp = when.astimezone().strftime("%Y-%m-%d")
96-    line = f"[{stamp}] {fact.strip()}\n"
97-    path = profile_path(root)
98-    path.parent.mkdir(parents=True, exist_ok=True)
99-    lock_path = path.parent / "profile.lock"
100-    try:
101-        lock_file = lock_path.open("a")
102-    except OSError as exc:
103-        raise OSError(f"Could not open profile lock file {lock_path}: {exc}") from exc
104-    try:
105-        try:
106-            fcntl.flock(lock_file, fcntl.LOCK_EX)
107-        except OSError as exc:
108-            raise OSError(f"Could not acquire profile lock {lock_path}: {exc}") from exc
109-        try:
110-            existing = path.read_text(encoding="utf-8") if path.is_file() else ""
111-            lines = _trim_profile_lines(existing.splitlines(keepends=True) + [line])
112-            atomic_text(path, "".join(lines))
113-        finally:
114-            fcntl.flock(lock_file, fcntl.LOCK_UN)
115-    finally:
116-        lock_file.close()
117-    return line.strip()
118-
119-
120-def parse_screenshot(text: str) -> str | None:
121-    match = SCREENSHOT.match((text or "").strip())
122-    if not match:
123-        return None
124-    target = (match.group(1) or "").strip()
125-    return target[:120] if target else ""
126-
127-
128-def _escape_applescript_string(value: str) -> str:
129-    return value.replace("\\", "\\\\").replace('"', '\\"')
130-
131-
132-def _macos_window_id(app_name: str) -> int | None:
133-    if sys.platform != "darwin":

--- new tests ---
295:    def test_trim_profile_lines_keeps_newest_under_budget(self):
296-        lines = [f"line-{i:05d}\n" for i in range(5000)]
297-        max_bytes = sum(len(entry.encode("utf-8")) for entry in lines[-100:])
298-        trimmed = _trim_profile_lines(lines, max_bytes=max_bytes)
299-        self.assertEqual(trimmed, lines[-100:])
300-        self.assertLessEqual(sum(len(e.encode("utf-8")) for e in trimmed), max_bytes)
301-
302:    def test_trim_profile_lines_noop_when_under_budget(self):
303-        lines = ["a\n", "b\n", "c\n"]
304-        self.assertEqual(_trim_profile_lines(lines, max_bytes=1000), lines)
305-
306:    def test_append_profile_memory_lock_open_failure_raises_oserror(self):
307-        with tempfile.TemporaryDirectory() as tmp:
308-            root = Path(tmp)
309-            lock_path = root / "bob-brain/memory/profile.lock"
310-            lock_path.mkdir(parents=True)
311-            with self.assertRaises(OSError) as ctx:
312-                append_profile_memory(root, "should not save")
313-            self.assertIn(str(lock_path), str(ctx.exception))
314-
315-    def test_prune_captures_enforces_max_count(self):
316-        with tempfile.TemporaryDirectory() as tmp:
317-            folder = Path(tmp)
318-            for index in range(5):
319-                path = folder / f"{index:016x}.png"
320-                path.write_bytes(b"png")
321-            now = time.time()
322-            for index, path in enumerate(sorted(folder.glob("*.png"))):
323-                stamp = now - (5 - index)
324-                os.utime(path, (stamp, stamp))
325-            _prune_captures(folder, max_count=2, max_age_days=365)
326-            remaining = list(folder.glob("*.png"))
327-            self.assertEqual(len(remaining), 2)
328-
329-    def test_format_web_search_reply_tolerates_missing_keys(self):
330-        self.assertEqual(format_web_search_reply({}), "")
331-        reply = format_web_search_reply({"heading": "Title", "source": "https://example.com"})

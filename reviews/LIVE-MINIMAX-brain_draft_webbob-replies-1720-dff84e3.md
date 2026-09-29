Looking at this diff for branch `brain/draft/webbob-replies-1720` (commit `dff84e3`), I'll perform a thorough code review against the stated goals: honest status naming every worker+task, plain-language job starts, short answer-first replies, texting draft->separate yes->send, voice barge-in, media on iPhone.

Let me trace through the key changes systematically:

---

# Code Review: webbob-replies-1720

## CRITICAL BUGS

### 1. **FATAL: `normalize_projects()` breaks compound project names**
**File:** `webchat/chat_intent.py:15-19`

```python
def normalize_projects(text):
    def correct(match):
        word = match[0].lower()
        choices = get_close_matches(word, ("webjam", "adoptiq", "storyboard"), n=2, cutoff=.86)
        return choices[0] if len(choices) == 1 else match[0]
    return re.sub(r"\b[A-Za-z]{6,10}\b", correct, text)
```

**Problem:** The regex `\b[A-Za-z]{6,10}\b` matches individual words. For "Storyland Fantasy Football" (the new project), it matches "Storyland" (9 chars) and tries to correct it via fuzzy matching to "webjam", "adoptiq", or "storyboard". This corrupts the project name before it can be properly matched.

**Impact:** "Storyland Fantasy Football" → corrupted → won't match `PROJECT_NAMES` → projects list empty → `project_start()` fails → jobs don't dispatch → goal "plain-language job starts" broken.

**Fix:**
```python
def normalize_projects(text):
    """Normalize compound project names, not prose words."""
    # Only correct full project name matches, not individual words
    def correct(match):
        word = re.sub(r"[\s-]+", "", match[0].lower())
        if word in PROJECT_NAMES:
            return PROJECT_NAMES[word]
        return match[0]
    return PROJECT.sub(correct, text)
```

---

### 2. **BUG: Missing cooldown info for non-primary workers**
**File:** `webchat/reply_authority.py:91-92`

```python
for name in ("codex", "claude", "cursor", "gemini", "minimax"):
    rows = [row for row in work if row.get("worker") == name]
    current = " | ".join(_work_line(row, detailed) for row in rows)
    if not current:
        current = "idle" if all(inspection.values()) else "activity unconfirmed"
    lines.append(WORKER_NAMES[name] + ": " + current + _cooldown(snap, name) + ".")  # _cooldown called here
# ...
other = [row for row in work if row.get("worker") not in ("codex", "claude", "cursor", "gemini", "minimax")]
if other:
    lines.append("Other sessions: " + " | ".join(_work_line(row, detailed) for row in other) + ".")  # NO _cooldown!
```

**Problem:** `_cooldown()` is not called for "other" workers. If a custom worker enters cooldown, the status reply won't show it.

**Impact:** Violates goal "honest status naming every worker+task".

**Fix:** Add `_cooldown()` call for other workers:
```python
if other:
    other_line = " | ".join(_work_line(row, detailed) for row in other)
    # Add cooldown info for other workers if any are in cooldown
    other_cooldown = [_cooldown(snap, row.get("worker", "")) for row in other]
    other_cooldown_info = "".join(set(c for c in other_cooldown if c))
    lines.append("Other sessions: " + other_line + other_cooldown_info + ".")
```

---

### 3. **BUG: Wrong key reference in `_work_line()` fallback**
**File:** `webchat/reply_authority.py:69`

```python
if not row.get("task"):
    label += " — " + (row.get("screen") or "process " + str(row.get("pid")))
    label += "; " + row["log_path"] + "; last: " + row["last_log_line"]
```

**Problem:** Should be `row.get("screen")` but uses hardcoded key. If `log_path` or `last_log_line` keys don't exist, this raises `KeyError`.

**Fix:**
```python
if not row.get("task"):
    label += " — " + (row.get("screen") or "process " + str(row.get("pid")))
    label += "; " + row.get("log_path", "") + "; last: " + row.get("last_log_line", "")
```

---

### 4. **BUG: Test assertion expects wrong call count**
**File:** `services/test_dispatch.py:387`

```python
self.assertEqual(ask.call_count, 3 if review == "Not JSON" else 2)
```

**Problem:** Based on `result_acceptance.py` retry logic, `ask` is called twice for ANY malformed response (first attempt + one retry), not three times. The conditional `3 if review == "Not JSON"` is never reachable in current code structure.

**Fix:**
```python
# Test should expect exactly 2 calls for malformed review (attempt + retry)
self.assertEqual(ask.call_count, 2)
```

---

## SECURITY ISSUES

### 5. **MEDIUM: Command injection in `gh()` function**
**File:** `services/draft_publish.py:50-52`

```python
def gh(*args):
    result = run(["gh", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60)
```

**Problem:** `cwd` is user-controlled via `row["publish_project"]` → `projects[project]["repo"]`. While path traversal is unlikely with `Path.resolve()`, malformed paths could cause unexpected behavior.

**Mitigation:** Already mitigated by using `subprocess.run` with explicit args list (not shell). Consider adding explicit path validation.

---

### 6. **LOW: Umask not restored in deploy script**
**File:** `webchat/deploy_replies.py:49`

```python
os.umask(0o077)
```

**Problem:** Umask is modified but never restored. While potentially intentional, this affects the entire process and could cause issues if deployment fails early.

**Fix:** Use context manager or restore:
```python
old_umask = os.umask(0o077)
try:
    # ... deployment logic ...
finally:
    os.umask(old_umask)
```

---

## MISSING TESTS

### 7. **Test gap: No test for single project start with `project_start()`**
**File:** `webchat/task_dispatch.py:236-243` (branch not covered)

```python
elif names and (PUSH.match(command(description)) or project_start(description)):
    package = project_plan(self.root, description, names, worker)[0]
    description, worker, kind = package["prompt"], package["worker"], package["kind"]
    publish_project = package.get("publish_project")
    draft_pr = package.get("draft_pr", False)
```

**Problem:** This branch handles "start up WebJam" (single project) but has no dedicated test.

**Fix:** Add test case in `test_chat_intent.py`:
```python
def test_single_project_start_creates_draft_pr(self):
    # "start up WebJam" should create draft PR
```

---

### 8. **Test gap: No test for `normalize_projects()` with compound names**
**File:** `webchat/chat_intent.py`

**Problem:** New function lacks unit tests for:
- "Storyland Fantasy Football" → should return unchanged
- "Stkryboard" → should NOT auto-correct (not in the limited choices list)
- "Fantasy-Football" → should normalize to "Fantasy Football"

---

### 9. **Test gap: No test for `_cooldown()` with various states**
**File:** `webchat/reply_authority.py`

**Problem:** `_cooldown()` has complex logic for merging `lane_locks` and `provider_health` that isn't tested.

---

## CORRECTNESS ISSUES

### 10. **Logic issue: `publish_project` not set for single project starts**
**File:** `webchat/task_dispatch.py:168-175`

```python
def project_plan(root, description, names, worker):
    # ...
    for project in names:
        # ...
        packages.append(dict(worker=lane, kind=kind, title=project, prompt=prompt,
                             publish_project=project if publish or starting else None, 
                             draft_pr=starting))
```

When `names = ["Fantasy Football"]` and `starting = True` (from `project_start()`), `publish_project` is set. However, the caller at line 238 only enters this branch if `names` is non-empty AND `(PUSH.match(...) or project_start(...))`. So this is actually correct.

---

### 11. **Potential: `cwd` could be None**
**File:** `services/dispatch_worker.py:150`

```python
if not task_queue.transition(ROOT, identifier, token, "executing", worktree=str(cwd) if cwd else None,
                             branch=branch, project=project, repo=str(repo) if repo else None,
                             prompt_file=str(folder / "prompt.txt")):
```

**Analysis:** `cwd` is set from `Path(row["worktree"])` earlier. If `worktree` key is missing from row, `row["worktree"]` returns `None`, and `Path(None)` raises `TypeError`. However, looking at `enqueue()`, `worktree` is never set there, so it defaults to `None`. The code should handle this.

**Fix:** Ensure `cwd` has a fallback:
```python
cwd = Path(row.get("worktree") or repo) if row.get("worktree") or repo else None
```

---

## SUMMARY TABLE

| Priority | Severity | File:Line | Issue |
|----------|----------|-----------|-------|
| P1 | CRITICAL | `chat_intent.py:15-19` | `normalize_projects()` corrupts compound names |
| P1 | CRITICAL | `chat_intent.py:32` | `project_start()` broken → no job starts |
| P2 | HIGH | `reply_authority.py:91-92` | Missing cooldown for "other" workers |
| P2 | HIGH | `reply_authority.py:69` | KeyError potential in fallback |
| P3 | MEDIUM | `test_dispatch.py:387` | Wrong assertion call count |
| P4 | LOW | `deploy_replies.py:49` | Umask not restored |
| P5 | LOW | `draft_publish.py:50` | Security hardening recommended |

---

## GOAL COMPLIANCE ANALYSIS

| Goal | Status | Notes |
|------|--------|-------|
| Honest status naming every worker+task | **PARTIAL** | Bug #2: Other workers missing cooldown info |
| Plain-language job starts | **BROKEN** | Bug #1: `normalize_projects()` breaks project detection |
| Short answer-first replies | ✓ | RULES updated correctly |
| Texting draft→separate yes→send | ✓ | `draft_pr` flow implemented |
| Voice barge-in | N/A | Not addressed in diff |
| Media on iPhone | N/A | Not addressed in diff |

---

# VERDICT: FAIL

**Reason:** Critical bug #1 (`normalize_projects()`) completely breaks the "plain-language job starts" goal for the new "Fantasy Football" project and any compound project names. The `project_start()` detection depends on `projects()` returning correct results, which is broken by the normalization function.

**Required fixes before merge:**
1. Fix `normalize_projects()` to only correct full project name matches
2. Add `_cooldown()` for "other" workers
3. Fix key error in `_work_line()`
4. Correct test assertion for call count
5. Add unit tests for new functions
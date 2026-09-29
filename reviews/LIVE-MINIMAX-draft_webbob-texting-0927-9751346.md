# Code Review: `draft/webbob-texting-0927` @ 9751346

## CRITICAL SEVERITY

### 1. Command Injection in `draft_publish.py`
**File:** `services/draft_publish.py:64-70`
```python
def gh(*args):
    result = run(["gh", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60)
```
**Issue:** User-controlled values `remote` and `branch` are passed directly to shell commands without sanitization. An attacker-controlled project name like `foo; rm -rf /` could execute arbitrary commands.

**Fix:**
```python
def gh(*args):
    # Validate inputs to prevent command injection
    safe_chars = re.compile(r'^[a-zA-Z0-9._/-]+$')
    for val in [remote, branch]:
        if not safe_chars.match(val):
            raise ValueError(f"Invalid input for gh command: {val}")
    result = run(["gh", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60)
```

### 2. Missing Import: `redact`
**File:** `services/dispatch_worker.py:153`
```python
atomic_write(folder / "prompt.txt", redact(prompt))
```
**Issue:** `redact` is called but not imported. Will raise `NameError` at runtime.

**Fix:** Add import at top of file:
```python
from webchat.redact import redact  # or wherever redact is defined
```

---

## HIGH SEVERITY

### 3. Potential None Reference in `dispatch_worker.py`
**File:** `services/dispatch_worker.py:152-155`
```python
if not task_queue.transition(ROOT, identifier, token, "executing", worktree=str(cwd) if cwd else None,
                             branch=branch, project=project, repo=str(repo) if repo else None,
                             prompt_file=str(folder / "prompt.txt")):
```
**Issue:** `cwd` can be `None` when fallback to `task_repository()` returns `("WebBob", Path(...))`. The `repo` may also be `None`. If `cwd` is `None`, `str(cwd) if cwd else None` is correct, but inconsistent with explicit `Path` handling elsewhere.

**Fix:**
```python
if not task_queue.transition(ROOT, identifier, token, "executing", 
                             worktree=str(cwd) if cwd else None,
                             branch=branch, project=project, 
                             repo=str(repo) if repo else None,
                             prompt_file=str(folder / "prompt.txt")):
```
Actually this is fine since it uses `str(cwd) if cwd else None` correctly. **NO CHANGE NEEDED.**

### 4. Project Validation Inconsistency
**File:** `state/task_queue.py:170`
```python
if publish_project is not None and (kind != "coding" or publish_project not in ("WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football", "Shelf", "Web Bob")):
```
**Issue:** `projects.json` defines `"shelf"` (lowercase) but validation checks `"Shelf"` (capitalized). Will reject valid `"shelf"` projects.

**Fix:**
```python
if publish_project is not None and (kind != "coding" or publish_project.lower() not in ("webjam", "adoptiq", "storyboard", "fantasy football", "shelf", "web bob")):
```

---

## MEDIUM SEVERITY

### 5. Retry Logic Variable Mutation
**File:** `services/result_acceptance.py:61-68`
```python
for attempt in range(2):
    try:
        # ...
    except json.JSONDecodeError as exc:
        if attempt:
            raise
        instructions = ("Your previous review..." + instructions)  # Mutates loop variable!
```
**Issue:** Modifying `instructions` inside loop is confusing and could cause issues if logic changes. Also, retry prepends but doesn't clarify the format requirement enough.

**Fix:**
```python
def _build_review_instructions(attempt, original_prompt):
    if attempt == 0:
        return original_prompt
    return ("Your previous review did not return parseable JSON. Do not use tools, inspect files, "
            "or narrate progress. Evaluate the supplied task and answer again. "
            "Return ONLY a JSON object with accepted (boolean) and reason (string).\n\n" + original_prompt)

for attempt in range(2):
    try:
        raw = review(_build_review_instructions(attempt, instructions)).strip()
        # ...
```

### 6. Missing Test: `project_catalog()`
**File:** `services/dispatch_worker.py:31-35`
**Issue:** New `project_catalog()` function has no unit tests covering its merge behavior when keys conflict.

**Fix:** Add test to verify local overrides ship defaults:
```python
def test_project_catalog_local_overrides_ship_defaults(self):
    with tempfile.TemporaryDirectory() as tmp:
        ship = Path(tmp) / "projects.json"
        local = Path(tmp) / "conductor" / "services" / "projects.json"
        local.parent.mkdir(); local.parent.mkdir(parents=True, exist_ok=True)
        ship.write_text(json.dumps({"A": {"repo": "~/.a"}}))
        local.write_text(json.dumps({"A": {"repo": "~/local"}}))
        with patch("dispatch_worker.CONDUCTOR", Path(tmp)):
            catalog = dispatch_worker.project_catalog()
            self.assertEqual(catalog["A"]["repo"], "~/local")
```

---

## LOW SEVERITY / MISSING TESTS

### 7. Missing Test: `ensure_draft_pr()` Idempotency Edge Cases
**File:** `services/draft_publish.py:52-80`
**Issue:** Test covers happy path and draft→undraft failure, but not race condition where two PRs exist.

### 8. Missing Test: `transition()` New Parameters
**File:** `services/dispatch_worker.py:154`
**Issue:** `worktree`, `branch`, `project`, `repo`, `prompt_file` parameters added to transition but not verified in test assertions.

### 9. Missing Test: `atomic_write` Prompt File
**File:** `services/dispatch_worker.py:153`
**Issue:** No test verifies prompt file content or handles write failures.

---

## GOAL COMPLIANCE GAPS

### Voice Barge-in: ❌ NOT IMPLEMENTED
No code changes for voice barge-in feature found in diff.

### Media on iPhone: ❌ NOT IMPLEMENTED  
No code changes for iPhone media handling found in diff.

---

## SUMMARY TABLE

| Severity | File:Line | Issue | Status |
|----------|-----------|-------|--------|
| CRITICAL | `draft_publish.py:64` | Command injection via unsanitized `remote`/`branch` | **UNFIXED** |
| CRITICAL | `dispatch_worker.py:153` | `redact` function not imported | **UNFIXED** |
| HIGH | `task_queue.py:170` | `"shelf"` vs `"Shelf"` case mismatch | **UNFIXED** |
| MEDIUM | `result_acceptance.py:61-68` | Variable mutation in retry loop | **UNFIXED** |
| MEDIUM | `dispatch_worker.py` | Missing tests for `project_catalog()` | **UNFIXED** |
| LOW | `draft_publish.py` | Missing race-condition test for PR creation | **UNFIXED** |
| GAP | - | Voice barge-in feature missing | **UNFIXED** |
| GAP | - | Media on iPhone feature missing | **UNFIXED** |

---

## VERDICT: FAIL

### Blocking Issues:
1. **Command injection vulnerability** - Cannot deploy with arbitrary command execution possible
2. **Missing import** - `NameError` at runtime will break all job execution
3. **Project validation bug** - Legitimate `"shelf"` projects will be rejected

### Additional Concerns:
- Voice barge-in and media on iPhone features (core goal requirements) are entirely absent
- 2 critical security/correctness issues must be fixed before approval

### Required Actions Before Re-review:
1. Sanitize `remote` and `branch` inputs in `ensure_draft_pr()`
2. Add `redact` import to `dispatch_worker.py`
3. Fix `"shelf"` case sensitivity in `task_queue.py`
4. Address voice/media feature gaps or provide timeline
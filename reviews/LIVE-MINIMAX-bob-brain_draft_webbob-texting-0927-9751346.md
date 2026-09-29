Looking at this diff, I need to identify actual code changes (not documentation/logs) and perform a strict security review. Let me analyze the implementation changes:

## Code Review Analysis

### ACTUAL CODE CHANGES IDENTIFIED:

1. `services/dispatch_worker.py` - Core dispatch logic
2. `services/draft_publish.py` - Draft PR creation
3. `services/result_acceptance.py` - Review retry logic
4. `state/task_queue.py` - Queue enqueue with draft_pr parameter
5. Tests for above

---

## BUGS (Critical Issues)

### BUG-1: `dispatch_worker.py` - Transition Call with Invalid Parameters
**Severity: CRASH**  
**File:** `services/dispatch_worker.py:152-155`

```python
if not task_queue.transition(ROOT, identifier, token, "executing", worktree=str(cwd) if cwd else None,
                             branch=branch, project=project, repo=str(repo) if repo else None,
                             prompt_file=str(folder / "prompt.txt")):
```

**Problem:** The `task_queue.transition()` function signature does NOT accept `worktree`, `branch`, `project`, `repo`, or `prompt_file` parameters. Examining `state/task_queue.py`, `transition()` only accepts `(root, identifier, token, new_status)`. These kwargs will cause `TypeError: transition() got unexpected keyword arguments`.

**Fix:**
```python
if not task_queue.transition(ROOT, identifier, token, "executing"):
```

The additional metadata should either be written separately or the `transition()` function should be extended to accept and store these fields.

---

### BUG-2: `result_acceptance.py` - Instructions Mutation Accumulation
**Severity: MEDIUM**  
**File:** `services/result_acceptance.py:59-68`

```python
for attempt in range(2):
    try:
        # ... 
        instructions = ("Your previous review..." + instructions)  # Prepends, never resets
    except json.JSONDecodeError as exc:
        if attempt:
            raise ResultRejected(...) from exc
        instructions = ("Your previous review..." + instructions)  # BUG: accumulates
```

**Problem:** If multiple retries occur (though `range(2)` limits to one retry), instructions keep growing. More critically, the retry instruction is prepended to the original, making the prompt longer than necessary.

**Fix:**
```python
def _build_review_instructions(task_prompt, answer, attempt=0):
    base = ("Your previous review did not return parseable JSON. " if attempt else "") + \
           "Do not use tools, inspect files, or narrate progress. " + \
           "Evaluate the supplied task and answer again. " + \
           'Return ONLY a JSON object with accepted (boolean) and reason (string).\n\n' + \
           json.dumps({"task": task_prompt, "answer": answer}, ensure_ascii=False)
    return base

# In accept():
for attempt in range(2):
    try:
        instructions = _build_review_instructions(prompt, answer, attempt)
        # ... use instructions ...
```

---

## SECURITY ISSUES

### SEC-1: `draft_publish.py` - GH CLI Injection Risk
**Severity: HIGH**  
**File:** `services/draft_publish.py:51-75`

```python
def gh(*args):
    result = run(["gh", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60)
    # ...
    return result.stdout.strip()

prs = existing()
if not prs:
    # ...
    gh("pr", "create", "--repo", remote, "--head", branch, "--draft", "--title",
       "Improve " + row["publish_project"] + " (Web Bob)", "--body-file", str(body))
```

**Problem:** `row["publish_project"]` and `row["id"]` are concatenated into command strings without sanitization. If these originate from user input or task definitions, shell injection is possible.

**Fix:**
```python
# Validate project name: alphanumeric, spaces, hyphens only
if not re.fullmatch(r'[\w\s-]+', row["publish_project"]):
    raise ValueError("Invalid project name")

# Use list args, not string interpolation
gh("pr", "create", "--repo", remote, "--head", branch, "--draft", 
   "--title", f"Improve {row['publish_project']} (Web Bob)", "--body-file", str(body))
```

---

### SEC-2: `draft_publish.py` - Error Message Information Leak
**Severity: MEDIUM**  
**File:** `services/draft_publish.py:52`

```python
if result.returncode:
    raise RuntimeError("Draft PR command failed: " + result.stderr[-500:])
```

**Problem:** `stderr` may contain file paths, token fragments, or GitHub API details. Taking the last 500 chars doesn't guarantee sanitization.

**Fix:**
```python
if result.returncode:
    # Sanitize: remove paths, tokens, URLs
    sanitized = re.sub(r'[/\\]\S+', '[PATH]', result.stderr)
    sanitized = re.sub(r'(ghp_|github_pat_)\w+', '[TOKEN]', sanitized)
    sanitized = re.sub(r'https?://\S+', '[URL]', sanitized)
    raise RuntimeError("Draft PR command failed (see logs for details)")
```

---

## MISSING TESTS

### T-1: No test for `draft_pr` parameter flow
**File:** `state/task_queue.py:169-171`

Add test:
```python
def test_draft_pr_requires_publish_project(self):
    with self.assertRaises(ValueError, msg="Draft PR requires a project publication"):
        queue.enqueue(self.root, "conv", "req", "Task", draft_pr=True)

def test_draft_pr_stored_in_row(self):
    row = queue.enqueue(self.root, "conv", "req", "Task", publish_project="WebJam", draft_pr=True)
    self.assertTrue(queue.tasks(self.root)[row["id"]]["draft_pr"])
```

---

### T-2: No test for `transition()` with metadata (currently broken)
**File:** `services/dispatch_worker.py:152`

Should verify `transition()` receives correct params. Currently fails due to BUG-1.

---

### T-3: No test for `project_catalog()` override precedence
**File:** `services/dispatch_worker.py:28-32`

Add test:
```python
def test_local_projects_override_shipped(self):
    # Shipped has "WebJam"; local has different path
    # Verify local path wins
```

---

## CODE QUALITY ISSUES

### Q-1: Unused `atomic_write` result in `dispatch_worker.py`
**File:** `services/dispatch_worker.py:151`
```python
atomic_write(folder / "prompt.txt", redact(prompt))  # Result unused
```
The prompt is written but never read. Either remove or document purpose.

---

### Q-2: Missing `draft_pr` handling in `transition()` metadata
**File:** `services/dispatch_worker.py:152`

The `draft_pr` field is stored in task rows but never used in `dispatch_worker.execute()`. The `ensure_draft_pr()` is called only when `row.get("draft_pr")` but this flow isn't tested end-to-end.

---

## SUMMARY TABLE

| ID | Severity | File:Line | Issue | Fix Required |
|----|----------|-----------|-------|--------------|
| BUG-1 | CRASH | `dispatch_worker.py:152-155` | `transition()` doesn't accept kwargs | Remove invalid kwargs or extend transition() |
| BUG-2 | MEDIUM | `result_acceptance.py:59-68` | Instructions accumulate on retry | Refactor to build fresh instructions |
| SEC-1 | HIGH | `draft_publish.py:64-67` | Shell injection via project names | Validate/sanitize input |
| SEC-2 | MEDIUM | `draft_publish.py:52` | stderr leaks paths/tokens | Sanitize error output |
| T-1 | TEST | `task_queue.py` | No `draft_pr` parameter tests | Add validation tests |
| T-2 | TEST | `dispatch_worker.py` | No metadata transition test | Add test (after BUG-1 fix) |
| Q-1 | LOW | `dispatch_worker.py:151` | Unused `atomic_write` result | Document or remove |

---

## VERDICT: FAIL

**Rationale:** BUG-1 is a **critical crash** that will cause immediate `TypeError` when any task transitions to "executing" state on this branch. The code cannot run. SEC-1 represents a potential shell injection vulnerability if project names are user-controlled. The missing tests for the new `draft_pr` parameter leave the critical texting->publish flow untested.

**Required before PASS:**
1. Fix BUG-1: Remove invalid kwargs from `transition()` call or extend the function
2. Fix SEC-1: Add input validation for project names
3. Add T-1: Test `draft_pr` parameter validation and storage
4. (Optional but recommended) Fix SEC-2 and BUG-2
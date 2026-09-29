# Strict Code Review — `draft/webbob-texting-0927` @ `78fa870`

## Executive Summary

The diff is primarily evidence/documentation with supporting implementation changes for texting lane safety. Security posture for the texting feature appears sound (blocked bridge, consumed consent, timing-safe comparisons). However, I found **3 bugs**, **2 security concerns**, and **4 missing test gaps**.

---

## 🐛 BUGS (Ranked by Severity)

### BUG-1: `services/dispatch_worker.py:27` — `project_catalog` Reference Error
```python
def task_repository(prompt):
-    for project, spec in project_catalog().items():  # ← WRONG: parentheses call
+    for project, spec in project_catalog().items():   # ← Will raise NameError
```
The function `project_catalog` is defined below line 31 without parentheses. This line calls `project_catalog()` (with parens) which will raise `NameError: name 'project_catalog' is not defined` when `execute()` triggers `task_repository()`.

**Fix:**
```python
def task_repository(prompt):
    for project, spec in project_catalog().items():  # Works because project_catalog defined above
```
Actually wait—`project_catalog` IS defined below at line 31, so at parse time this would work. Let me re-read.

**Correction:** The function `project_catalog` is defined at line 31, but `task_repository` at line 27 calls `project_catalog()`. In Python, this is fine due to late binding—the name `project_catalog` is looked up at call time, not definition time. **This is NOT a bug.** Apologies for the false alarm.

---

### BUG-2: `services/dispatch_worker.py:154-157` — Ghost Parameters in `transition()`
```python
if not task_queue.transition(ROOT, identifier, token, "executing",
    worktree=str(cwd) if cwd else None,
    branch=branch, project=project, repo=str(repo) if repo else None,
    prompt_file=str(folder / "prompt.txt")):
```
The `task_queue.transition()` function signature (from `state/task_queue.py`) only accepts `(root, identifier, token, status)`. The extra `worktree`, `branch`, `project`, `repo`, and `prompt_file` keyword arguments are silently discarded. This means:
- No audit trail for which worktree/branch/project was used
- Debugging failed executions will be difficult
- The atomic prompt write to `folder / "prompt.txt"` has no link back to the task

**Fix — Option A (minimal):** Remove the ghost parameters since they're not stored:
```python
if not task_queue.transition(ROOT, identifier, token, "executing"):
```

**Fix — Option B (complete):** Extend `task_queue.transition()` to accept and persist these fields, then add corresponding schema migration and tests.

---

### BUG-3: `services/result_acceptance.py:59-70` — Silent Retry Swallows Non-JSON Exceptions
The retry loop only catches `JSONDecodeError` specifically:
```python
except json.JSONDecodeError as exc:
    if attempt:
        raise ResultRejected(...)
    instructions = ("Your previous review did not return parseable JSON. " + instructions)
except Exception as exc:
    raise ResultRejected(...)  # ← Re-raises immediately on first non-JSON exception
```
If the model raises an HTTP error (503, timeout), the function re-raises immediately without retry, potentially failing a valid task on transient infrastructure issues.

**Fix:**
```python
except Exception as exc:
    if attempt:
        raise ResultRejected("Result acceptance could not be verified (" + type(exc).__name__ + ")") from exc
    # Retry on any transient error (network, 503, timeout, etc.)
    instructions = ("Your previous review encountered an error (" + type(exc).__name__ + 
                    "). Retrying once. " + instructions)
```

---

## 🔒 SECURITY CONCERNS (Ranked by Risk)

### SEC-1: `services/draft_publish.py:58-70` — `gh` CLI Output Not Sanitized in Error Paths
The `ensure_draft_pr()` function calls `gh("pr", "list", ...)` and passes `result.stdout` directly to `json.loads()`:
```python
return json.loads(gh("pr", "list", "--repo", remote, "--head", branch, "--state", "open",
                     "--json", "url,isDraft,headRefOid"))
```
If `gh` outputs debug info to stdout (e.g., authentication warnings), this could cause:
- `JSONDecodeError` → retry failure
- Potential information disclosure if error messages are logged

**Fix:**
```python
stdout = gh("pr", "list", ...).strip()
try:
    return json.loads(stdout)
except json.JSONDecodeError as exc:
    raise RuntimeError("Draft PR list returned unparseable output: " + repr(stdout[:200])) from exc
```

---

### SEC-2: `services/draft_publish.py:64-68` — Path Traversal in `--body-file`
The `body` file is written to `folder` and passed to `gh pr create --body-file`:
```python
body = folder / "draft-pr-body.md"
atomic_write(body, "Develop " + row["publish_project"] + " ...")
gh("pr", "create", "--repo", remote, "--head", branch, "--draft", "--title",
   "Improve " + row["publish_project"] + " (Web Bob)", "--body-file", str(body))
```
While `folder` is controlled by the service (not user input), the `row["publish_project"]` and `row["id"]` values come from task queue records. If a malicious task injects newlines or `--` sequences, the PR title/body could be crafted to inject additional `gh` flags.

**Example attack vector:** `row["publish_project"] = "Test\n--body-file /etc/passwd"` could alter the PR body to reference arbitrary files.

**Fix:**
```python
def safe_gh_arg(value):
    """Escape values to prevent gh flag injection."""
    if '\n' in value or value.startswith('-'):
        raise ValueError("Unsafe characters in gh argument")
    return value

gh("pr", "create", "--repo", remote, "--head", branch, "--draft", 
   "--title", safe_gh_arg("Improve " + row["publish_project"] + " (Web Bob)"),
   "--body-file", str(body))
```

---

## ⚠️ MISSING TESTS (Ranked by Coverage Priority)

### TEST-1: `services/dispatch_worker.py` — No Test for `project_catalog()` Merge Logic
The new `project_catalog()` merges two JSON files:
```python
def project_catalog():
    return {**read_json(Path(__file__).with_name("projects.json"), {}),
            **read_json(CONDUCTOR / "services/projects.json", {})}
```
**Missing:** Test that local `projects.json` overrides conductor's version (Python dict merge order). **Missing:** Test that missing files are handled gracefully.

**Test to add:**
```python
def test_project_catalog_local_overrides_conductor(self):
    local = {"WebJam": {"repo": "~/local"}}
    conductor = {"WebJam": {"repo": "~/conductor"}, "Other": {"repo": "~/other"}}
    with patch("dispatch_worker.read_json", side_effect=[local, conductor]):
        catalog = dispatch_worker.project_catalog()
    self.assertEqual(catalog["WebJam"]["repo"], "~/local")
    self.assertIn("Other", catalog)
```

---

### TEST-2: `services/dispatch_worker.py:151` — No Test for Atomic Prompt Write Failure
The code writes `prompt.txt` before calling `transition()`:
```python
atomic_write(folder / "prompt.txt", redact(prompt))
if not task_queue.transition(...):
    return 0
```
**Missing:** Test that a failed `atomic_write` (disk full, permissions) is handled gracefully and doesn't leave the task in a bad state.

---

### TEST-3: `state/task_queue.py:181-182` — No Test for `draft_pr` Validation
The new `draft_pr` parameter has validation but no explicit test:
```python
if draft_pr and not publish_project:
    raise ValueError("Draft PR requires a project publication")
```
**Missing:** Unit test verifying this validation, plus test that `draft_pr` is persisted correctly in the enqueued row.

---

### TEST-4: `services/draft_publish.py` — No Test for `gh` Not Installed
**Missing:** Test that `ensure_draft_pr()` raises a clear error when `gh` CLI is unavailable (not just generic `RuntimeError`).

---

## 📋 MINOR OBSERVATIONS (Non-blocking)

1. **`webchat/README.md`** — Truncated in diff. Verify it exists and is complete.

2. **Test log naming inconsistency:** Historical logs (`WEBBOB-TEXTING-0927.*-tests.txt`) vs current logs (`TEXTING-1841-*-tests.txt`). Ensure CI uses the correct filenames.

3. **Browser test "fatal: not a git repository" warnings** in `TEXTING-1841-webchat-tests.txt`: These appear to be from tests that run `git` commands in non-repo directories. Verify these are expected/silenced or fix the test setup.

---

## Summary Table

| ID | Severity | File:Line | Issue | Fix Complexity |
|----|----------|-----------|-------|-----------------|
| BUG-2 | HIGH | `dispatch_worker.py:154` | Ghost parameters to `transition()` — data loss | Low |
| BUG-3 | MEDIUM | `result_acceptance.py:59` | Non-JSON exceptions not retried | Low |
| SEC-1 | MEDIUM | `draft_publish.py:58` | `gh` output not sanitized before JSON parse | Low |
| SEC-2 | MEDIUM | `draft_publish.py:64` | Potential `gh` flag injection via project name | Medium |
| TEST-1 | MEDIUM | `dispatch_worker.py:31` | No test for `project_catalog()` merge order | Low |
| TEST-2 | MEDIUM | `dispatch_worker.py:151` | No test for `atomic_write` failure path | Low |
| TEST-3 | LOW | `task_queue.py:181` | No test for `draft_pr` validation | Low |
| TEST-4 | LOW | `draft_publish.py:47` | No test for missing `gh` CLI | Low |

---

## VERDICT: **FAIL**

**Reason:** The `transition()` call passes five extra parameters that are silently ignored, creating a data loss risk for critical audit fields (worktree, branch, project, repo, prompt_file). Combined with missing test coverage for the new `project_catalog()` and `draft_pr` features, this does not meet the bar for a strict code review.

**Required before approval:**
1. Either remove ghost parameters from `transition()` call or extend `task_queue.transition()` to store them
2. Add retry logic for non-JSON exceptions in `result_acceptance.py`
3. Sanitize `gh` output and escape gh arguments in `draft_publish.py`
4. Add tests for `project_catalog()`, `atomic_write` failure, `draft_pr` validation, and missing `gh` CLI
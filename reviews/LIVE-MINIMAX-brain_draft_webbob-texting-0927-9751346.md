# Code Review: `draft/webbob-texting-0927` @ 9751346

## Executive Summary

The branch introduces texting lane fixes (consume consent, browser proof, public data filtering), draft PR creation, and project catalog merging. Tests pass. However, I identified **2 correctness bugs**, **1 security concern**, and **2 missing tests** that require fixes before PASS.

---

## 🔴 CRITICAL / CORRECTNESS BUGS

### 1. `draft_publish.py:ensure_draft_pr` — Race Condition Creates Duplicate Draft PRs
**Severity:** HIGH  
**File:** `services/draft_publish.py`  
**Lines:** 51-70

```python
def existing():
    return json.loads(gh("pr", "list", "--repo", remote, "--head", branch, "--state", "open",
                         "--json", "url,isDraft,headRefOid"))
prs = existing()
if not prs:   # <-- RACE WINDOW: another concurrent caller or manual PR creation wins
    # ... create PR ...
    prs = existing()  # verifies our PR only
```

**Problem:** Between `existing()` and `gh("pr", "create")`, a concurrent `ensure_draft_pr()` call or external PR creation can satisfy the `if not prs` guard, causing duplicate draft PRs. The verification after creation (`len(prs) != 1`) then fails with `RuntimeError`, breaking valid workflows.

**Fix:**
```python
def ensure_draft_pr(row, cwd, folder, remote, branch, sha):
    def gh(*args):
        # ... unchanged ...
    def existing():
        return json.loads(gh("pr", "list", "--repo", remote, "--head", branch, "--state", "open",
                             "--json", "url,isDraft,headRefOid"))
    
    # Check-and-create must be atomic via retry, or use lockfile
    for attempt in range(3):
        prs = existing()
        if len(prs) == 1 and prs[0]["isDraft"] and prs[0]["headRefOid"] == sha:
            return prs[0]["url"]
        if not prs:
            body = folder / "draft-pr-body.md"
            # ... create PR ...
            continue  # re-check in next iteration
        raise RuntimeError("Unexpected PR state: " + str(prs))
    raise RuntimeError("Could not establish draft PR after 3 attempts")
```

---

### 2. `dispatch_worker.py:transition()` — `worktree="None"` When `cwd` Is Absent
**Severity:** MEDIUM  
**File:** `services/dispatch_worker.py`  
**Line:** 153

```python
if not task_queue.transition(ROOT, identifier, token, "executing", worktree=str(cwd) if cwd else None, ...):
```

**Problem:** When `cwd` is `None`, `worktree` is set to the **string** `"None"`. This stores `"None"` literally in the task record instead of `null`/`None`. Downstream consumers comparing `worktree is None` will behave incorrectly (string `"None"` is truthy).

**Fix:**
```python
worktree=str(cwd) if cwd else None,  # Explicit: None stays None
```

---

## 🟡 SECURITY CONCERNS

### 3. `result_acceptance.py` — Retry Prompt Ineffective Against Model Tool Use
**Severity:** MEDIUM  
**File:** `services/result_acceptance.py`  
**Lines:** 66-71

```python
instructions = ("Your previous review did not return parseable JSON. Do not use tools, inspect files, "
                "or narrate progress. Evaluate the supplied task and answer again. "
                "Return ONLY a JSON object with accepted (boolean) and reason (string).\n\n" + instructions)
```

**Problem:** The constraint "Do not use tools" is advisory text only. A misbehaving or jailbroken model can ignore it and use tools during retry, potentially inspecting the task artifact or codebase—violating the isolation principle for result acceptance.

**Fix Options:**
1. **Preferable:** Make the retry reviewer a separate, constrained inference call that explicitly disables tools (if your provider supports this).
2. **Minimum:** Log when tools appear during acceptance retries and fail-closed on detection.

---

## 🟠 MISSING TESTS

### 4. `test_result_acceptance.py` — No Coverage for Non-JSONDecodeError Exceptions
**Severity:** LOW  
**File:** `services/test_result_acceptance.py`

The new retry logic covers `JSONDecodeError`, but the `except Exception` branch that immediately fails is untested.

**Add:**
```python
def test_non_json_exception_always_fails_without_retry(self):
    review = Mock(side_effect=RuntimeError("Provider outage"))
    with self.assertRaisesRegex(ResultRejected, "RuntimeError"):
        accept("Fix bug", "Fixed it", review)
    self.assertEqual(review.call_count, 1)  # No retry
```

---

### 5. `test_draft_publish.py` — No Coverage for Concurrent PR Creation Race
**Severity:** MEDIUM (matches Bug #1)

The `test_project_pr_is_created_once_as_draft_and_never_undrafted` test verifies idempotency against sequential calls but not concurrent callers.

**Add:**
```python
def test_ensure_draft_pr_race_concurrent_creation(self):
    sha, branch = "a" * 40, "draft/webchat-" + "a" * 32
    row = dict(id=branch.removeprefix("draft/"), publish_project="Test")
    created = []
    def fake_concurrent(*args, **kwargs):
        if args[1:3] == ["pr", "create"]:
            created.append(1)
            return subprocess.CompletedProcess(args, 0, json.dumps([]), "")  # Simulate other caller created PR first
        return subprocess.CompletedProcess(args, 0, json.dumps([{"url": "http://x", "isDraft": True, "headRefOid": sha}]), "")
    
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        with patch.object(draft_publish, "run", side_effect=fake_concurrent):
            result = draft_publish.ensure_draft_pr(row, folder, folder, "o/r", branch, sha)
            # Should recover and return existing PR, not raise
            self.assertEqual(result, "http://x")
```

---

## ✅ OTHER OBSERVATIONS (NOT BLOCKING)

| Item | File | Note |
|------|------|------|
| `subprocess.DEVNULL` | `draft_publish.py:41` | `capture_output=True` already suppresses stderr; the explicit `stderr=...` is redundant but harmless. |
| Tuple semantics | `dispatch_worker.py:27` | `task_repository()` returns `(project_name, repo_path)`. The variable named `project` holds the **repo name** (e.g., "WebJam"). Confusing but consistent. |
| Hardcoded allowlist | `task_queue.py:172` | `"Fantasy Football"` added to `publish_project` validation. Maintainers must keep in sync with `projects.json`. Consider dynamic validation. |
| `StopIteration` risk | `test_dispatch.py:89` | `next(row for row in ... if row["status"] == "running")` raises if queue is empty. Defensive `next(..., None)` preferred. |
| `read_json` error handling | `dispatch_worker.py:34` | If either `projects.json` is malformed, `project_catalog()` raises. No graceful degradation. |

---

## 📋 TEST RESULTS SUMMARY

| Suite | Result | Notes |
|-------|--------|-------|
| `webchat` unittest (292 tests) | ✅ PASS | |
| `services` unittest (121 tests) | ✅ PASS | |
| Targeted texting (33 tests) | ✅ PASS | |
| `node --check app.js` | ✅ PASS | |
| `node --check browser_texting.cjs` | ✅ PASS | |
| `python3 bootstrap.py check` | ✅ PASS | |

---

## VERDICT

**FAIL**

**Reason:** Bug #1 (duplicate draft PR race condition) can cause deployment pipeline failures in concurrent scenarios. Bug #2 (`worktree="None"` stored as string) corrupts task metadata semantics. Both are correctness issues in production code paths.

**Required before PASS:**
1. Fix race condition in `ensure_draft_pr` (Bug #1)
2. Fix `worktree` parameter when `cwd` is `None` (Bug #2)
3. Add test for non-JSONDecodeError exception path (Item #4)
4. Add concurrency test for draft PR creation (Item #5)

**Optional/Recommended:**
- Address advisory constraint in retry prompt (Item #3)
- Add defensive `StopIteration` handling in test mock
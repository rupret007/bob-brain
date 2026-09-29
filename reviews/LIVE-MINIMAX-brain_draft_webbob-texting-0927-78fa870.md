# Strict Code Review: `brain/draft/webbob-texting-0927` @ `78fa870`

## Overview
This diff adds texting lane features to Web Bob and updates dispatch/publish workflow. Reviewing against the stated goal (honest status naming every worker+task, plain-language job starts, short answer-first replies, texting draft→separate yes→send, voice barge-in, media on iPhone).

---

## 🔴 CRITICAL (Security / Data Loss)

### 1. `services/dispatch_worker.py:150` — Prompt Written Before Transition Validation

**Severity:** CRITICAL — Data integrity / inconsistent state

```python
atomic_write(folder / "prompt.txt", redact(prompt))        # ← written first
if not task_queue.transition(ROOT, identifier, token, "executing", ...):  # ← checked second
    return 0
```

If `transition()` returns `False` (task already claimed, invalid token, etc.), the function returns `0` but `prompt.txt` is already on disk. This creates:
- Orphaned prompt files for unstarted tasks
- Mismatch between task queue state and filesystem

**Fix:**
```python
if not task_queue.transition(ROOT, identifier, token, "executing",
                             worktree=str(cwd) if cwd else None,
                             branch=branch, project=project,
                             repo=str(repo) if repo else None,
                             prompt_file=str(folder / "prompt.txt")):
    return 0
atomic_write(folder / "prompt.txt", redact(prompt))
```

---

### 2. `services/dispatch_worker.py:28-32` — Unrestricted Local Config Override

**Severity:** HIGH — Privilege escalation / arbitrary code execution

```python
def project_catalog():
    return {**read_json(Path(__file__).with_name("projects.json"), {}),
            **read_json(CONDUCTOR / "services/projects.json", {})}  # ← local OVERRIDES shipped
```

Any user with write access to `CONDUCTOR/services/projects.json` can override shipped project mappings. A malicious entry could redirect code execution:

```json
{"../../tmp/evil": {"repo": "~/MaliciousRepo", "remote": "attacker/repo"}}
```

**Fix:**
```python
def project_catalog():
    shipped = read_json(Path(__file__).with_name("projects.json"), {})
    # Local config EXTENDS, never overrides, shipped keys
    local = read_json(CONDUCTOR / "services/projects.json", {})
    for key, val in local.items():
        shipped.setdefault(key, val)
    return shipped
```

---

### 3. `services/draft_publish.py:62` — Branch Name Injection in `gh` CLI

**Severity:** MEDIUM — Command injection (low probability but no sanitization)

```python
gh("pr", "create", "--repo", remote, "--head", branch, "--draft", ...)
```

`branch` comes from `row["branch"]` with no validation. While typically system-generated, if any user input reaches this path, branch names with spaces, quotes, or newlines could cause unexpected `gh` behavior.

**Fix:**
```python
if not re.match(r'^[a-zA-Z0-9._/-]+$', branch):
    raise ValueError("Invalid branch name")
```

---

### 4. `state/task_queue.py:199` — `draft_pr` Not Validated as Boolean

**Severity:** MEDIUM — State corruption

```python
draft_pr=row.get("draft_pr", False),  # ← any truthy value accepted
```

No type check. Strings like `"true"`, `1`, or objects could enter the queue.

**Fix:**
```python
draft_pr=bool(draft_pr) if draft_pr else False,
```

---

## 🟡 MEDIUM (Logic Bugs / Test Failures)

### 5. `services/test_dispatch.py:84` — Wrong Keyword Argument in Assertion

**Severity:** MEDIUM — Test is checking the wrong parameter

```python
self.assertEqual(current["worktree"], str(kwargs["cwd"]))  # ← expects "cwd"
```

But the code at `dispatch_worker.py:154` passes `worktree=...`:

```python
task_queue.transition(ROOT, identifier, token, "executing",
                      worktree=str(cwd) if cwd else None, ...)  # ← passes "worktree"
```

This test will **always fail** against the actual implementation. The assertion should check `kwargs["worktree"]`.

**Fix:**
```python
self.assertEqual(current["worktree"], str(kwargs["worktree"]))
```

---

### 6. `services/test_draft_publish.py:28-48` — Test Mock Always Returns Empty List for `gh pr list`

**Severity:** MEDIUM — Test doesn't exercise the "existing PR" path correctly

```python
def fake(argv, **kwargs):
    calls.append(argv)
    if argv[1:3] == ["pr", "create"]:
        ...
        prs.append(record)
    return subprocess.CompletedProcess(argv, 0, json.dumps(prs), "")  # ← always dumps current prs
```

When `argv[1:3] == ["pr", "list"]` (first call), `prs` is `[]`, so `json.dumps([])` is returned. The function then uses `json.loads()` on this, which works but always returns `[]` for the first call. This is actually correct for the "no existing PR" case, but the test structure is fragile.

**Fix:** Explicitly handle list vs create:
```python
def fake(argv, **kwargs):
    calls.append(argv)
    if argv[1:3] == ["pr", "list"]:
        return subprocess.CompletedProcess(argv, 0, json.dumps(prs), "")
    if argv[1:3] == ["pr", "create"]:
        ...
        prs.append(record)
        return subprocess.CompletedProcess(argv, 0, "", "")
```

---

### 7. `services/dispatch_worker.py:197-199` — PR URL Prepending Without Verification

**Severity:** LOW — User experience / information disclosure

```python
if publication.get("pr_url"):
    answer = "Draft PR: " + publication["pr_url"] + "\n" + answer
```

This prepends a URL to the answer. If `ensure_draft_pr()` returns a valid URL but the PR creation failed later (or the URL is malformed), the user gets misleading information.

**Fix:** Add verification or make this conditional on explicit success:
```python
if publication.get("pr_url"):
    # Only prepend if we can verify the PR exists
    answer = f"Draft PR created: {publication['pr_url']}\n\n{answer}"
```

---

## ⚪ LOW (Missing Test Coverage)

### 8. `services/dispatch_worker.py` — No Test for `project_catalog()` Override Behavior

The new `project_catalog()` function merges configs but has no unit test verifying:
- Shipped keys are present
- Local keys extend (not override) shipped keys
- Duplicate keys use shipped values

**Missing test:**
```python
def test_project_catalog_local_extends_not_overrides_shipped(self):
    shipped = {"WebJam": {"repo": "~/orig"}}
    local = {"WebJam": {"repo": "~/override"}, "NewProject": {"repo": "~/new"}}
    with patch("dispatch_worker.read_json", side_effect=[shipped, local]):
        catalog = dispatch_worker.project_catalog()
    self.assertEqual(catalog["WebJam"]["repo"], "~/orig")  # shipped preserved
    self.assertIn("NewProject", catalog)  # local added
```

---

### 9. `services/draft_publish.py` — No Test for `ensure_draft_pr` Branch Injection

No test verifies that malformed branch names are rejected or sanitized.

**Missing test:**
```python
def test_ensure_draft_pr_rejects_invalid_branch(self):
    row = dict(id="test", publish_project="Test")
    with self.assertRaises(ValueError):
        draft_publish.ensure_draft_pr(row, Path("/tmp"), Path("/tmp"), 
                                      "owner/repo", "branch; rm -rf /", "a" * 40)
```

---

## 📊 Summary Table

| # | File:Line | Severity | Issue | Fix Required |
|---|-----------|----------|-------|--------------|
| 1 | `dispatch_worker.py:150` | 🔴 CRITICAL | Prompt written before transition check | Reorder atomic_write after transition |
| 2 | `dispatch_worker.py:28-32` | 🔴 HIGH | Local config overrides shipped projects | Use setdefault instead of merge |
| 3 | `draft_publish.py:62` | 🟡 MEDIUM | Branch name not sanitized | Add regex validation |
| 4 | `task_queue.py:199` | 🟡 MEDIUM | `draft_pr` not boolean-validated | Cast to bool |
| 5 | `test_dispatch.py:84` | 🟡 MEDIUM | Wrong kwarg in test assertion | Use "worktree" not "cwd" |
| 6 | `test_draft_publish.py:28` | 🟡 MEDIUM | Fragile mock return logic | Explicit list vs create handling |
| 7 | `dispatch_worker.py:197` | ⚪ LOW | PR URL prepended without verification | Add verification or conditional |
| 8 | `dispatch_worker.py` | ⚪ LOW | Missing `project_catalog()` tests | Add unit test for merge behavior |
| 9 | `draft_publish.py` | ⚪ LOW | Missing branch injection test | Add negative test case |

---

## VERDICT: **FAIL**

**Rationale:**
1. **CRITICAL**: `dispatch_worker.py:150` writes prompt to disk before validating the transition succeeds — this can leave orphaned files and inconsistent state.
2. **HIGH**: `project_catalog()` allows local config to override shipped project mappings, creating a privilege-escalation vector.
3. **MEDIUM**: Test at `test_dispatch.py:84` checks the wrong keyword argument and will fail against the actual implementation.

**Blocking issues #1, #2, and #5 must be fixed before this branch can be merged.** The other issues should be addressed in follow-up commits to improve robustness.
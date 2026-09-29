# Code Review: `draft/webbob-texting-0927` @ 78fa870

## Priority Rankings

| Priority | Severity | Category | Location | Issue |
|----------|----------|----------|----------|-------|
| **P0** | 🔴 Critical | NameError / Broken Code | `services/dispatch_worker.py:150` | `REPOS` undefined |
| **P0** | 🔴 Critical | Security / Broken Test | `services/test_dispatch.py:386` | String-vs-Mock comparison always false |
| P1 | 🔴 Critical | Logic Bug | `services/dispatch_worker.py:28-32` | `project_catalog()` merge order is backwards |
| P2 | 🟡 Medium | Logic Bug | `services/dispatch_worker.py:150` | `repo=` param to `transition()` is wrong |
| P2 | 🟡 Medium | Logic Bug | `services/dispatch_worker.py:150` | `worktree` vs `cwd` mismatch risk |
| P3 | 🟢 Low | Test Gap | `state/task_queue.py:184-185` | No test for `draft_pr` deduplication |
| P3 | 🟢 Low | Test Gap | `services/dispatch_worker.py` | Missing test for `task_catalog()` override precedence |
| P4 | ⚪ Info | Code Quality | `services/dispatch_worker.py:150` | `prompt.txt` write has no rollback on failure |

---

## P0 — CRITICAL: `REPOS` Undefined

**File:** `services/dispatch_worker.py:150`
```python
# transition call at line ~152:
if not task_queue.transition(ROOT, identifier, token, "executing",
    worktree=str(cwd) if cwd else None,
    branch=branch,
    project=project,
    repo=str(repo) if repo else None,  # ← REPOS used here?
    prompt_file=str(folder / "prompt.txt")):
```

The `transition()` call passes a parameter named `repo`. In the surrounding scope, `REPOS` appears to be referenced as the source of project repository paths (from `project_catalog()`). The variable `REPOS` is **not imported, not defined, and not in scope**. This will raise `NameError: name 'REPOS' is not defined` at runtime when `transition()` is called.

**Fix:** Either define `REPOS = project_catalog()` near the top of `execute()`, or pass the resolved repository path directly. Example fix:

```python
# Near the top of execute(), after extracting row:
REPOS = project_catalog()
# ... existing code ...
# Then in the transition call, remove the broken repo= line or correct it:
repo_path = REPOS.get(project, {}).get("repo")
```

---

## P0 — CRITICAL: String-vs-Mock Comparison in Test Always False

**File:** `services/test_dispatch.py:386`
```python
self.assertEqual(ask.call_count, 3 if review == "Not JSON" else 2)
```

`review` is a `Mock` object (the test parameter), **not the string** `"Not JSON"`. The comparison `review == "Not JSON"` is always `False`, so the assertion will **always** expect 2 calls, never 3. This means:
1. The retry-on-malformed-review logic in `result_acceptance.py` is not being tested
2. The test passes even if the retry logic is broken

**Fix:**
```python
self.assertEqual(ask.call_count, 3 if review.side_effect and
                 isinstance(review.side_effect, list) else 2)
# OR: pass a real string "Not JSON" as the side_effect in the relevant test case
```

---

## P1 — CRITICAL: `project_catalog()` Merge Order Backwards

**File:** `services/dispatch_worker.py:28-32`
```python
def project_catalog():
    # Ship new project mappings with the pinned release; retain local overrides.
    return {**read_json(Path(__file__).with_name("projects.json"), {}),
            **read_json(CONDUCTOR / "services/projects.json", {})}
```

**Problem:** Python dict unpacking `**a, **b` means keys in `b` override keys in `a`. Here:
- `a` = shipped projects.json (the "pinned release")
- `b` = CONDUCTOR override projects.json

The comment says "retain local overrides" but the **pinned release takes precedence over local overrides** (because `a` is left operand). If a mini owner has added a local project override, it will be **silently shadowed** by the shipped version on next deploy.

**Fix — swap order so local overrides win:**
```python
def project_catalog():
    # Ship new project mappings with the pinned release; local overrides take precedence.
    return {**read_json(Path(__file__).with_name("projects.json"), {}),   # shipped defaults
            **read_json(CONDUCTOR / "services/projects.json", {})}         # local overrides WIN
```

---

## P2 — MEDIUM: `repo=` Parameter to `transition()` Is Wrong

**File:** `services/dispatch_worker.py:150`
```python
task_queue.transition(ROOT, identifier, token, "executing",
    worktree=str(cwd) if cwd else None,
    branch=branch,
    project=project,
    repo=str(repo) if repo else None,  # ← 'repo' is a project name or URL string, NOT a path
    prompt_file=str(folder / "prompt.txt"))
```

The variable `repo` in scope is a string key from `project_catalog()` (e.g., `"owner/project"` or a repo path). It is **not a filesystem path**. `transition()` likely expects a real repository path for auditing. Without seeing `transition()` signature, this is likely passing garbage.

**Fix:**
```python
# Pass the actual resolved repo path, not the catalog key:
task_queue.transition(ROOT, identifier, token, "executing",
    worktree=str(cwd) if cwd else None,
    branch=branch,
    project=project,
    repo=str(repo_path) if repo_path else None,  # repo_path = Path(spec["repo"]).expanduser().resolve()
    prompt_file=str(folder / "prompt.txt"))
```

---

## P2 — MEDIUM: `worktree` vs `cwd` Mismatch Risk

**File:** `services/dispatch_worker.py:150`

`worktree=str(cwd) if cwd else None` — if `cwd` is ever `None` (unexpected), the task record gets `worktree=None` instead of a real path. This should probably fail-closed rather than pass `None`.

**Fix:**
```python
if not cwd:
    raise RuntimeError("Cannot execute without a worktree")
task_queue.transition(ROOT, identifier, token, "executing",
    worktree=str(cwd),
    ...
```

---

## P3 — LOW: Missing Test for `draft_pr` Deduplication

**File:** `state/task_queue.py:184-185`

The deduplication comparison now includes `row.get("draft_pr", False)`:
```python
row.get("draft_pr", False)) != (prompt, worker, ..., draft_pr):
```

There is **no test** verifying that a second `enqueue()` with the same `request_id` but different `draft_pr` raises `ValueError`. The existing tests only cover `publish_project` deduplication.

**Fix — add test:**
```python
def test_draft_pr_different_values_raises_on_same_request_id(self):
    queue.enqueue(self.root, "conv", "same-id", "Do it", publish_project="WebJam")
    with self.assertRaises(ValueError):
        queue.enqueue(self.root, "conv", "same-id", "Do it",
                      publish_project="WebJam", draft_pr=True)
```

---

## P3 — LOW: Missing Test for `project_catalog()` Override Precedence

**File:** `services/dispatch_worker.py:28-32`

No test verifies that local `CONDUCTOR/services/projects.json` overrides the shipped `projects.json`. Given the P1 bug above, this is especially important.

**Fix — add test:**
```python
def test_project_catalog_local_overrides_win(self):
    (CONDUCTOR / "services").mkdir(parents=True)
    (CONDUCTOR / "services/projects.json").write_text(json.dumps({"WebJam": {"repo": "/override/path"}}))
    catalog = dispatch_worker.project_catalog()
    self.assertEqual(catalog["WebJam"]["repo"], "/override/path")
```

---

## P4 — INFO: `prompt.txt` Write Has No Rollback on Failure

**File:** `services/dispatch_worker.py:150`
```python
atomic_write(folder / "prompt.txt", redact(prompt))
if not task_queue.transition(...):
```

If `atomic_write` succeeds but `transition()` fails, the `prompt.txt` file remains on disk as orphaned audit data. Minor concern but worth noting.

---

## Missing Test Summary

| Test | File | Priority |
|------|------|----------|
| `draft_pr=True` deduplication conflict | `state/task_queue.py` | P3 |
| `project_catalog()` override precedence | `services/dispatch_worker.py` | P3 |
| `transition()` called with correct `repo` path | `services/dispatch_worker.py` | P3 |
| `transition()` called with correct `worktree` (not None) | `services/dispatch_worker.py` | P3 |

---

## VERDICT: **FAIL**

**Rationale:**
1. **P0 — `REPOS` undefined**: Code will crash with `NameError` on any job execution.
2. **P0 — String-vs-Mock test bug**: The retry-on-malformed-review feature is not actually being tested; the test is passing incorrectly.
3. **P1 — Merge order backwards**: Local project overrides are silently lost on deploy, violating the documented intent.

The branch cannot be deployed until P0 items are resolved. The retry logic is not covered by its own test (due to the Mock comparison bug), creating a regression risk.

**Required before re-review:**
1. Define `REPOS` (or equivalent resolved catalog) in `execute()` scope.
2. Fix `review == "Not JSON"` → proper conditional based on test setup.
3. Swap `project_catalog()` dict merge order.
4. Add test demonstrating local override precedence.
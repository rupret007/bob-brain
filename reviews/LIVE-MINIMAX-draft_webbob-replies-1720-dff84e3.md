Looking at this diff, I'll perform a thorough code review focusing on bugs, security issues, and missing tests.

## CRITICAL BUGS

### 1. **dispatch_worker.py:151-154** - Transition parameters ignored, execution metadata lost
```python
if not task_queue.transition(ROOT, identifier, token, "executing", worktree=str(cwd) if cwd else None,
                             branch=branch, project=project, repo=str(repo) if repo else None,
                             prompt_file=str(folder / "prompt.txt")):
```
**Issue**: `transition()` is called with extra kwargs (`worktree`, `branch`, `project`, `repo`, `prompt_file`), but these are not stored. The subsequent `mini_worker.execute(row)` or `ask()` call receives the original `row` without this metadata. The test at `test_dispatch.py:75` expects `current["worktree"]` to be populated, but it won't be.

**Fix**: Store execution metadata in the row before calling workers:
```python
row.update(worktree=str(cwd) if cwd else None, branch=branch, project=project, repo=str(repo) if repo else None)
atomic_write(folder / "prompt.txt", redact(prompt))
if not task_queue.transition(ROOT, identifier, token, "executing"):
    return 0
answer = redact(mini_worker.execute(row) if row["worker"] == "mini" else ask(row["worker"], prompt, cwd=cwd, ...))
```

---

### 2. **result_acceptance.py:58-72** - Retry logic catches wrong exception
```python
except json.JSONDecodeError as exc:
    if attempt:
        raise ResultRejected(...)
    instructions = (...)
```
**Issue**: The retry block only catches `JSONDecodeError`, but if `review()` returns a dict instead of str, `raw.strip()` throws `AttributeError`, which falls through to the outer `except` and fails immediately without retry.

**Fix**:
```python
except (json.JSONDecodeError, AttributeError, TypeError) as exc:
    if attempt or not isinstance(raw, str):
        raise ResultRejected("Result acceptance could not be verified (JSONDecodeError)") from exc
    instructions = ("Your previous review did not return parseable JSON..."
```

---

### 3. **test_result_acceptance.py:17-21** - Test expects wrong exception
```python
review = Mock(return_value='{"accepted": false, "reason": "Missing the requested fix"}')
with self.assertRaisesRegex(ResultRejected, "did not complete"):
    accept("Fix visibility", "I plan to fix it", review)
```
**Issue**: `accept()` returns `verdict` when `accepted=false`; it only raises `ResultRejected` on parse/validation failures. This test will fail because no exception is raised.

**Fix**: Change test expectation:
```python
result = accept("Fix visibility", "I plan to fix it", review)
self.assertFalse(result["accepted"])
self.assertEqual(review.call_count, 1)
```

---

## SECURITY ISSUES

### 4. **chat_intent.py:34-37** - Typo correction to wrong project
```python
def normalize_projects(text):
    def correct(match):
        word = match[0].lower()
        choices = get_close_matches(word, ("webjam", "adoptiq", "storyboard"), n=2, cutoff=.86)
        return choices[0] if len(choices) == 1 else match[0]
```
**Issue**: Only 3 of 6 projects in `PROJECT_NAMES` are in the typo-correction dictionary. "Storyland Fantasy Football" → could correct to "StoryBoard" (similar substring). "Fantasy Football" cannot be auto-corrected. "Shelf" cannot be corrected.

**Fix**: Add missing projects:
```python
choices = get_close_matches(word, ("webjam", "adoptiq", "storyboard", "fantasyfootball", "shelf"), ...)
```

---

### 5. **services/dispatch_worker.py:110** - Credential leak potential
```python
atomic_write(folder / "prompt.txt", redact(prompt))
```
**Issue**: `redact()` is called but not defined in this file. If it fails or is misconfigured, sensitive content from `prompt` (which may contain API keys, repo URLs, tokens) could be written to disk unredacted.

**Fix**: Ensure `redact` is properly imported and tested, or inline sensitive-value redaction:
```python
from conductor import redact  # or define minimal redact for prompts
```

---

## LOGIC BUGS

### 6. **dispatch_worker.py:27-31** - project_catalog() merge order contradicts comment
```python
def project_catalog():
    # Ship new project mappings with the pinned release; retain local overrides.
    return {**read_json(Path(__file__).with_name("projects.json"), {}),
            **read_json(CONDUCTOR / "services/projects.json", {})}
```
**Issue**: Comment says "retain local overrides" (services/projects.json should win), but dict unpacking means the FIRST file (project.json) wins. Local overrides are lost.

**Fix**: Reverse merge order:
```python
return {**read_json(CONDUCTOR / "services/projects.json", {}),
        **read_json(Path(__file__).with_name("projects.json"), {})}
```

---

### 7. **task_dispatch.py:144-146** - project substitution lambda broken
```python
scoped = PROJECT.sub(lambda match: project if projects(match[0]) == [project]
                     else "another project", normalize_projects(description))
```
**Issue**: `PROJECT` regex matches "web jam" (with space) from input, but `projects()` normalizes to "webjam" key. If the match text isn't in `PROJECT_NAMES` keys (e.g., "Fantasy Football" space variant), returns empty list.

**Fix**: Normalize match text before lookup:
```python
def _project_sub(match, target_project):
    normalized = re.sub(r"[\s-]+", "", match[0].lower())
    key = PROJECT_NAMES.get(normalized)
    return target_project if key == target_project else "another project"
scoped = PROJECT.sub(lambda m: _project_sub(m, project), description)
```

---

### 8. **reply_authority.py:65-66** - Unreachable code
```python
if not row.get("task") and "task" in row:
    label += " — " + (row.get("screen") or "process " + str(row.get("pid")))
```
**Issue**: `row.get("task")` returns `None` if key missing OR if value is `None`. `"task" in row` only True if key exists with value `None` or falsy. This combination is almost never True (would require `{"task": None}` specifically).

**Fix**: Simplify:
```python
if not row.get("task"):
    label += " — " + (row.get("screen") or "process " + str(row.get("pid")))
```

---

## MISSING TESTS

### 9. **chat_intent.py** - No test for `normalize_projects()` typo correction
```python
def test_normalize_projects_typo_correction():
    # "Webjma" → "webjam" (suggested)
    # "Storyland Fantasy Fotball" → "fantasyfootball" match
    # "Shelf" → no suggestion (not in choices)
```

---

### 10. **reply_authority.py** - No test for `correcting_status()` edge cases
```python
def test_correcting_status_consecutive_criticisms():
    # Two criticisms in a row should not crash
    conv = {"messages": [
        {"role": "user", "content": "What's running?"},
        {"role": "user", "content": "This is bad"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "This needs improvement"}
    ]}
    assert correcting_status("This is worse", conv) == False  # No prior status Q
```

---

### 11. **dispatch_worker.py** - No test for `project_catalog()` merge order
```python
def test_project_catalog_local_overrides_pinned():
    # services/projects.json should override projects.json
```

---

### 12. **test_replies_session.py:132** - Typo: `self.col` undefined
```python
self.submit(self.identifier, text, request or str(uuid.uuid4()), **kwargs)
self.col  # Should be self.chat
```
**Issue**: `AttributeError: 'Fixture' object has no attribute 'col'`

---

## MINOR ISSUES

### 13. **deploy_replies.py:119** - Password passed as path object
```python
client = Client(client.url, client.password_file)  # Should be .read_text()
```
If `Client` expects string content, not Path, this fails.

---

### 14. **webchat/fixtures/replies_session_0927.json** - Fixture has hardcoded "Stkryboard" typo
```json
"Ok we want it to start up at max all the projects..."
```
Should test typo handling explicitly.

---

## SUMMARY

| Severity | File | Line(s) | Issue |
|----------|------|---------|-------|
| CRITICAL | services/dispatch_worker.py | 151-154 | Transition params ignored, worktree lost |
| CRITICAL | services/result_acceptance.py | 58-72 | Wrong exception caught, no retry |
| CRITICAL | test_result_acceptance.py | 17-21 | Test expects non-existent exception |
| HIGH | chat_intent.py | 34-37 | Incomplete typo dictionary |
| HIGH | services/dispatch_worker.py | 27-31 | Merge order reverses intent |
| HIGH | task_dispatch.py | 144-146 | Project substitution broken |
| MEDIUM | reply_authority.py | 65-66 | Unreachable code |
| MEDIUM | test_replies_session.py | 132 | `self.col` typo |
| LOW | deploy_replies.py | 119 | Path vs string |
| LOW | fixtures | - | Missing typo test data |

---

## VERDICT: FAIL

**Reason**: Three critical bugs prevent correct operation:
1. Execution metadata (worktree, branch, project) is passed to `transition()` but never stored in the row, breaking worker isolation and test assertions
2. The JSON retry logic catches `JSONDecodeError` but not the `AttributeError` from non-string review responses, defeating retry behavior
3. The test file expects `ResultRejected` for rejected verdicts, but the implementation returns them instead of raising

These must be fixed before the branch can pass integration testing.
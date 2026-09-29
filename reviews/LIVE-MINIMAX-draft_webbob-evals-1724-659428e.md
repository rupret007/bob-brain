# Strict Code Review: Web Bob Branch draft/webbob-evals-1724 @ 659428e

## Summary
This branch introduces evaluation infrastructure (mining scripts, reply builder, eval cases) to measure reply quality against Bob the Bot standards. The eval results show 24/41 passing (58.5%), indicating significant gaps.

---

## CRITICAL BUGS

### 1. `webchat/reply_builder.py:58` — `StubProviders.reply()` ignores conversation context
```python
def reply(self, conversation, cancel, progress):
    self.calls += 1
    progress("gemini", [])
    return dict(content=self.content, provider="gemini", attempts=[])
```
**Issue**: The `conversation` parameter is completely ignored. All prompts receive identical responses regardless of content. This defeats the purpose of offline reply testing.

**Fix**:
```python
def reply(self, conversation, cancel, progress):
    self.calls += 1
    progress("gemini", [])
    # In real implementation, this would route to appropriate handler
    # For testing, return the stub content
    content = self.content
    return dict(content=content, provider="gemini", attempts=[])
```
**Severity**: HIGH — Renders offline testing unreliable.

---

### 2. `webchat/reply_builder.py:21` — `ReplyOutcome` dataclass missing `passed` field
The eval expects each row to have a `passed` boolean, but `ReplyOutcome` only tracks raw data. The scoring logic must be external.

**Fix**: Add computation or import scoring logic:
```python
@dataclass
class ReplyOutcome:
    # ... existing fields ...
    
    def evaluate(self, rubrics: list[str]) -> bool:
        """Check if this reply passes all rubrics."""
        # Implementation depends on rubric definitions
        pass
```
**Severity**: MEDIUM — Missing integration point.

---

## SECURITY ISSUES

### 3. `webchat/mine_reply_eval_cases.py:22-23` — Path traversal via parent traversal
```python
CODE_ROOT.parent.parent / "conductor/webchat/sessions",
```
**Issue**: Traverses two parent directories, could escape repository bounds via symlinks or unusual layouts. No validation that resolved path is within CODE_ROOT.

**Fix**:
```python
def session_dir() -> Path:
    candidates = [
        CODE_ROOT / "conductor/webchat/sessions",
        CODE_ROOT.parent.parent / "conductor/webchat/sessions",
    ]
    for candidate in candidates:
        if candidate.is_dir() and candidate.resolve().is_relative_to(CODE_ROOT.resolve()):
            return candidate
    raise SystemExit("No conductor/webchat/sessions directory found for mining.")
```
**Severity**: MEDIUM — Read-only script but poor hygiene.

---

### 4. `webchat/mine_reply_eval_cases.py:19` — Overly broad SKIP pattern
```python
SKIP = re.compile(
    r"^Reply with exactly:|^From BOB-STATE and handback only:|^start lane |E2E0927|"
    r"^Debug this chat connection|^Connection check:|^Browser connection check|playwright ping",
    re.I,
)
```
**Issue**: `E2E0927` could match legitimate prompts containing "e2e0927" as project identifiers.

**Fix**:
```python
SKIP = re.compile(
    r"^Reply with exactly:|^From BOB-STATE and handback only:|^start lane |"
    r"^Debug this chat connection|^Connection check:|^Browser connection check|playwright ping",
    re.I,
)
```
**Severity**: LOW — Could cause false negatives in eval mining.

---

## LOGIC BUGS

### 5. `webchat/mine_reply_eval_cases.py:107-111` — Typo variants missing stub fixtures
```python
for case in list(cases):
    if case["category"] != "llm" or "what's" not in case["prompt"].lower():
        continue
    typo = re.sub(r"what's", "whats", case["prompt"], flags=re.I)
    add("typo", typo, case["session"] + "-typo", fixture=case.get("fixture"))
```
**Issue**: Copied `llm` cases get a fixture for state context but no `stub_model` (unlike MANUAL entries for start-01/criticism-02). This causes eval mismatch: typo-01 has `stub: "Here is a direct answer: WebJam draft #161 is still open."` but the mined variants won't have this.

**Fix**:
```python
for case in list(cases):
    if case["category"] != "llm" or "what's" not in case["prompt"].lower():
        continue
    typo = re.sub(r"what's", "whats", case["prompt"], flags=re.I)
    add("typo", typo, case["session"] + "-typo", 
        fixture=case.get("fixture"), 
        stub=case.get("stub_model"))  # Copy stub from parent case
```
**Severity**: MEDIUM — Typo eval cases won't match expected responses.

---

### 6. `webchat/mine_reply_eval_cases.py:116-117` — Inconsistent stub naming
```python
if stub:
    row["stub_model"] = stub
```
**Issue**: `add()` parameter is `stub` but stored as `stub_model`. Inconsistent naming could cause confusion.

**Fix**: Use consistent naming throughout.

---

### 7. `webchat/reply_builder.py:69` — `_seed_eval_root` defined but never called
```python
def _seed_eval_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
```
**Issue**: Dead code. If this is intended for setup, it's not integrated.

**Fix**: Either integrate into `main()` or remove:
```python
# Call before running eval
if __name__ == "__main__":
    # Seed test data if needed
    _seed_eval_root(Path(".reply-eval-runtime"))
    main()
```
**Severity**: LOW — Technical debt.

---

## MISSING TESTS

### 8. `webchat/mine_reply_eval_cases.py` — No unit tests
**Issue**: New file with complex pattern matching, regex filtering, and fixture assignment has zero test coverage.

**Fix**: Add tests covering:
- Pattern matching for each category
- SKIP regex filtering
- Stub/fixture assignment
- Minimum case count enforcement

---

### 9. `webchat/reply_builder.py` — No unit tests
**Issue**: Core evaluation infrastructure has no tests.

**Fix**: Add tests for:
- `StubProviders` behavior
- `ReplyOutcome` serialization
- Integration with `Chat` and `task_queue` mocks

---

### 10. Integration tests for eval loop missing
**Issue**: No end-to-end test that runs the full eval pipeline: mine cases → build replies → score → output results.

**Fix**: Add `tests/test_reply_eval_pipeline.py`.

---

## ROOT CAUSE ANALYSIS: Eval Failures

The eval failures stem from code under test (not the eval framework itself):

| Failure Type | Count | Root Cause |
|-------------|-------|------------|
| `status_max_lines` > 8 | 12 | State provider includes verbose uptime details |
| `action_creates_jobs` | 5 | Dispatcher/Gemini defer without queuing |
| `not_status_only` | 5 | Same as above |
| `no_empty_promises` | 2 | Gemini gives hollow acknowledgment |
| `answer_first` | 1 | Gemini opens with deferral |
| `version_short_sha` | 1 | Gemini returns draft reference, not SHA |

**Key insight**: The eval framework is correctly identifying failures. The fixes needed are in the reply providers, not the eval code.

---

## ADDITIONAL OBSERVATIONS

### 11. `reviews/WEBBOB-EVALS-0927.json` — Baseline mismatch
```json
"baseline": "dcc2c8e",
```
The commit being reviewed is `659428e`, but eval baseline is `dcc2c8e`. This is intentional for A/B comparison but should be documented.

### 12. `.gitignore` entries
```gitignore
!.reply-eval-runtime/
```
Temporary runtime directory is properly ignored. ✓

### 13. `reply_builder.py:10` — Mock import safety
```python
from test_worker_activity import PS, SCREENS
```
This import will fail if `test_worker_activity.py` doesn't exist or has import errors. Consider adding a graceful fallback:
```python
try:
    from test_worker_activity import PS, SCREENS
except ImportError:
    PS, SCREENS = {}, []
```

---

## VERDICT: **FAIL**

### Rationale:
1. **Critical bug**: `StubProviders.reply()` ignores conversation, making offline testing unreliable
2. **Security issue**: Path traversal in session directory detection
3. **Logic bug**: Typo variants missing stub fixtures (causes eval mismatches)
4. **Missing tests**: Zero test coverage on new infrastructure code
5. **Dead code**: `_seed_eval_root()` never called

### Required Before Merge:
- [ ] Fix `StubProviders.reply()` to properly route conversation
- [ ] Add `evaluate()` method to `ReplyOutcome`
- [ ] Fix path traversal vulnerability
- [ ] Add stub fixtures to typo variants
- [ ] Add unit tests for `mine_reply_eval_cases.py`
- [ ] Add unit tests for `reply_builder.py`
- [ ] Either integrate or remove `_seed_eval_root()`

The eval framework is conceptually sound and correctly identifies failures in the reply providers, but the implementation has critical gaps that prevent reliable offline evaluation.
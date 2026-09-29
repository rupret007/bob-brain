Looking at this diff, I need to analyze the new files added for the webbob-evals-1724 branch. Let me examine the code for bugs, security issues, and missing tests.

## Code Review

### CRITICAL BUGS

**1. webchat/reply_builder.py:24-34 — StubProviders.reply() ignores cancel/conversation, misleads tests**
```python
def reply(self, conversation, cancel, progress):
    self.calls += 1
    progress("gemini", [])  # Hardcoded provider!
    return dict(content=self.content, provider="gemini", attempts=[])
```
The stub **always** reports "gemini" regardless of actual provider, and ignores `conversation`/`cancel`. Tests using this stub will not catch bugs in provider routing or cancel handling.

**Fix:** Add `provider` parameter to StubProviders and make `reply` accept actual routing:
```python
def reply(self, conversation, cancel, progress):
    self.calls += 1
    provider = getattr(self, 'provider', 'gemini')
    progress(provider, [])
    return dict(content=self.content, provider=provider, attempts=[])
```

---

**2. webchat/reply_builder.py:47-50 — Path traversal in _seed_eval_root**
```python
def _seed_eval_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
```
The `root` parameter is not validated. If passed with `../` traversal, could create directories outside intended scope. No security boundary enforcement.

**Fix:** Add validation:
```python
def _seed_eval_root(root: Path) -> None:
    if not root.is_relative_to(Path(__file__).resolve().parent):
        raise ValueError(f"eval_root must be within webchat: {root}")
    root.mkdir(parents=True, exist_ok=True)
```

---

**3. webchat/mine_reply_eval_cases.py:29-31 — Unvalidated path traversal**
```python
for candidate in (
    CODE_ROOT / "conductor/webchat/sessions",
    CODE_ROOT.parent.parent / "conductor/webchat/sessions",
):
```
`CODE_ROOT.parent.parent` traversal is unbounded. Malicious symlinks could redirect to arbitrary locations.

**Fix:** Validate candidate paths stay within project:
```python
for candidate in (
    CODE_ROOT / "conductor/webchat/sessions",
):
    if (CODE_ROOT.parent / "conductor/webchat/sessions").is_dir():
        candidate = CODE_ROOT.parent / "conductor/webchat/sessions"
        break
```

---

**4. webchat/mine_reply_eval_cases.py:105-114 — Silent error swallowing**
```python
for path in sorted(session_dir().glob("*.json")):
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        continue  # Silently ignores ALL errors including permission, disk full, corruption
```
This masks security-relevant errors like permission denied or disk issues that should surface.

**Fix:**
```python
try:
    data = json.loads(path.read_text())
except json.JSONDecodeError:
    print(f"WARN: Skipping malformed JSON: {path}", file=sys.stderr)
    continue
except OSError as e:
    print(f"ERROR: Cannot read {path}: {e}", file=sys.stderr)
    raise  # Re-raise OSErrors - permission/disk issues should stop the run
```

---

**5. webchat/mine_reply_eval_cases.py:91-98 — Hardcoded stub responses bypass real logic**
```python
stub = (
    "Okay, I'll focus on getting all the projects running at full capacity."
    if category == "start" and "start up all" in prompt
    else "I understand. I'll focus on providing more detailed and useful updates."
    if category == "criticism" and "way better" in prompt
    else None
)
```
These hardcoded stubs in test fixtures don't exercise real prompt handling. The eval "passes" on fabricated responses, not actual system behavior.

---

### SECURITY ISSUES

**6. .gitignore — New exclusions allow bypassing secrets scanning**
```
+!webchat/reply_eval_cases.json
+!reviews/WEBBOB-EVALS-0927.json
```
If these JSON files contain API keys, eval data, or PII in future commits, they bypass standard ignore patterns. No mention of ensuring these files don't contain secrets.

**Fix:** Add to .gitignore header comment:
```gitignore
# NOTE: Ensure reply_eval_cases.json and WEBBOB-EVALS-*.json
# NEVER contain API keys, tokens, or PII before adding ! prefix
```

---

**7. webchat/reply_builder.py — No authentication/authorization in offline mode**
The offline reply builder doesn't validate session ownership. Any code that can import this module can simulate replies for any conversation_id.

**Fix:** Add session validation or mark as test-only with `if __name__ != "__main__"` guard.

---

### MISSING TESTS

**8. No unit tests for rubrics_for() logic**
`webchat/mine_reply_eval_cases.py:56-73` has complex conditional logic for different categories but no test coverage to verify rubrics match expected schema.

**Fix:** Add test cases:
```python
def test_rubrics_for_status():
    assert "status_max_lines" in rubrics_for("status")
    assert "action_creates_jobs" not in rubrics_for("status")

def test_rubrics_for_start():
    assert "action_creates_jobs" in rubrics_for("start")
    assert "status_max_lines" not in rubrics_for("start")
```

---

**9. No tests for StubProviders health/reply contracts**
`webchat/reply_builder.py` defines `StubProviders` but doesn't verify it implements the expected provider interface correctly.

**Fix:** Add interface test:
```python
def test_stub_providers_interface():
    stub = StubProviders()
    result = stub.reply(conversation={}, cancel=threading.Event(), progress=lambda *a: None)
    assert "content" in result
    assert "provider" in result
```

---

**10. No integration test for reply_builder ↔ task_dispatch**
The reply_builder imports `task_dispatch` but doesn't verify that jobs created through it appear in the actual queue or get properly attributed.

---

### SUMMARY TABLE

| Severity | File:Line | Issue | Category |
|----------|-----------|-------|----------|
| CRITICAL | reply_builder.py:24 | StubProviders hardcodes "gemini", ignores cancel | Bug |
| CRITICAL | reply_builder.py:47 | Unvalidated path in _seed_eval_root | Security |
| HIGH | mine_reply_eval_cases.py:29 | Unbounded parent traversal | Security |
| HIGH | mine_reply_eval_cases.py:105 | Silent error swallowing | Bug |
| HIGH | mine_reply_eval_cases.py:91 | Hardcoded stubs bypass real logic | Test Quality |
| MEDIUM | .gitignore:30 | Secrets bypass risk | Security |
| MEDIUM | reply_builder.py | No auth on offline mode | Security |
| LOW | mine_reply_eval_cases.py:56 | rubrics_for() inconsistent return types | Code Quality |
| LOW | mine_reply_eval_cases.py:116 | Apostrophe stripping creates false positives | Bug |

---

### GOAL COMPLIANCE CHECK

The branch goal is "match/beat Bob the Bot: honest status naming every worker+task, plain-language job starts, short answer-first replies, texting draft->separate yes->send, voice barge-in, media on iPhone".

**Findings:**
- **Status naming**: Eval tests check `status_max_lines` but NOT whether worker/task names are honest. Test "llm-03" shows 12 lines with names like "Projects push", "Web Bob clean" but no test verifies these names are accurate.
- **Job starts**: Tests verify `action_creates_jobs` but not "plain-language" requirement.
- **Draft->yes->send**: "text" category has `draft_only_no_send` rubric but no test verifies the separate reply flow.
- **Voice barge-in / media on iPhone**: **Zero coverage** in evals.

The eval framework exists but the **rubrics don't fully cover the stated goals**.

---

## VERDICT: FAIL

**Reason:** The code has critical bugs (hardcoded stubs, unvalidated paths), security issues (path traversal, no auth), and missing tests. Additionally, the eval framework doesn't cover voice barge-in or media handling, and status naming honesty is not verified. The hardcoded stub responses in particular make the 24/41 passing score unreliable as a measure of actual system quality.
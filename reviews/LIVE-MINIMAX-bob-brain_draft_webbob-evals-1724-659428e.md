# Code Review: bob-brain/draft/webbob-evals-1724 @ 659428e

## Summary
This branch adds eval infrastructure (test mining + reply builder) + evaluation results. Core functionality issues identified in the eval results must be fixed; there are also code-level bugs in the new scripts.

---

## CRITICAL Issues (Blockers)

### 1. Missing `else` in `rubrics_for()` — KeyError on unknown categories
**File:** `webchat/mine_reply_eval_cases.py:58`
```python
def rubrics_for(category: str) -> list[str]:
    base = ["answer_first", "no_unknown_task", "no_magic_prefix", "no_empty_promises"]
    if category in ("status", "llm"):
        base.append("status_max_lines")
    if category == "llm":
        base.append("reset_attribution")
    if category == "start":
        return ["answer_first", "no_magic_prefix", "no_empty_promises", "action_creates_jobs", "not_status_only"]
    # ... more explicit categories ...
    # NO else: falls through to return base
    return base  # Line 58 — but unreachable if all explicit cases return
```
**Fix:** Add `else: return base` after all explicit if-chains, or restructure as `elif/else`.

**Severity:** HIGH — silently returns `None` for unknown categories, causing downstream KeyError or silent rubric loss.

---

### 2. `status_max_lines` Exceeded in 14/41 Eval Cases — Functional Bug
**File:** `webchat/reply_builder.py` (implicit via `state` provider)

The `state` provider consistently outputs 9-12 lines where max is 8. This is the single largest failure category.

| Cases Affected | Lines | Max |
|----------------|-------|-----|
| llm-03, llm-05, status-03 | 12 | 8 |
| status-08, llm-06 | 11 | 8 |
| llm-04 | 10 | 8 |
| status-01, status-02, status-05, status-07 | 9 | 8 |

**Fix:** Implement line-limiting in status output generation (likely in `state` provider's reply builder).

**Severity:** HIGH — violates core quality requirement (short answer-first replies).

---

### 3. `action_creates_jobs` Failing — Dispatcher Not Confirming Jobs
**File:** Multiple eval cases: start-01, start-08, start-10, start-13, start-15

The dispatcher replies with status-only messages instead of server-confirmed job IDs:
- start-08: "Priority order: Web Bob..." (no job)
- start-10: "Ready when you are." (no job)
- start-13: "Here is a direct answer: WebJam draft #161" (wrong provider)

**Fix:** Ensure dispatcher correctly intercepts "start" category prompts and queues jobs, returning job IDs.

**Severity:** HIGH — core "plain-language job starts" requirement broken.

---

## HIGH Issues

### 4. Unsafe Path Traversal in `session_dir()`
**File:** `webchat/mine_reply_eval_cases.py:18-24`
```python
def session_dir() -> Path:
    for candidate in (
        CODE_ROOT / "conductor/webchat/sessions",
        CODE_ROOT.parent.parent / "conductor/webchat/sessions",
    ):
        if candidate.is_dir():
            return candidate
    raise SystemExit(...)
```
**Issue:** `parents[2]` could traverse outside repo if directory structure changes. No canonical path validation.

**Fix:**
```python
def session_dir() -> Path:
    for candidate in (
        CODE_ROOT / "conductor/webchat/sessions",
        CODE_ROOT / ".." / "conductor/webchat/sessions",  # relative only
    ):
        resolved = candidate.resolve()
        # Ensure it's within CODE_ROOT
        try:
            resolved.relative_to(CODE_ROOT.resolve())
        except ValueError:
            continue
        if candidate.is_dir():
            return candidate
```

**Severity:** MEDIUM — only affects dev machine if repo structure is manipulated, but should be defensive.

---

### 5. No Atomic Write in Output File
**File:** `webchat/mine_reply_eval_cases.py:146`
```python
OUT.write_text(json.dumps(..., indent=2) + "\n")
```
**Issue:** If process is killed mid-write, corrupt JSON left in place. No backup/atomic swap.

**Fix:**
```python
temp = OUT.with_suffix('.tmp')
temp.write_text(json.dumps(..., indent=2) + "\n")
temp.replace(OUT)
```

**Severity:** MEDIUM — eval data loss/corruption risk.

---

### 6. Hardcoded Baseline SHA Drift Risk
**File:** `webchat/mine_reply_eval_cases.py:144`
```python
OUT.write_text(json.dumps(dict(baseline_sha="dcc2c8e", cases=cases), indent=2) + "\n")
```
**Issue:** SHA hardcoded in two places (`baseline` in eval JSON and `"dcc2c8e"` here). If baseline changes, mining produces inconsistent data.

**Fix:** Single source of truth:
```python
BASELINE_SHA = "dcc2c8e"
# ... in main():
OUT.write_text(json.dumps(dict(baseline_sha=BASELINE_SHA, cases=cases), indent=2) + "\n")
```

**Severity:** MEDIUM — silent inconsistency risk.

---

### 7. Regex Patterns Not Raw Strings
**File:** `webchat/mine_reply_eval_cases.py:33-46`

Patterns like `r"\b"` are correct, but mixed with string literals in `SKIP`:
```python
SKIP = re.compile(
    r"^Reply with exactly:|^From BOB-STATE...",  # raw
    re.I,
)
```
**Issue:** `\b` in raw strings is correct, but non-raw string `"start lane "` in manual test data could cause issues. Currently safe but fragile.

**Fix:** Ensure all regex patterns use raw strings consistently.

**Severity:** LOW — currently safe due to Python string escaping, but could break if special chars added.

---

### 8. `StubProviders` Import Assumes Live Modules
**File:** `webchat/reply_builder.py:54-64`
```python
from app import Chat
from task_dispatch import task_queue
from test_worker_activity import PS, SCREENS
```
**Issue:** These imports may fail in offline eval context if modules have side-effects on import (db connections, signal handlers, etc.).

**Fix:** Add try/except with clear error message:
```python
try:
    from app import Chat
    from task_dispatch import task_queue
    from test_worker_activity import PS, SCREENS
except ImportError as e:
    raise ImportError(f"Required for reply_builder: {e}") from e
```

**Severity:** MEDIUM — build/test breakage risk.

---

### 9. Missing Test Coverage for `reply_builder.py`
**File:** `webchat/reply_builder.py`

No unit tests for:
- `ReplyOutcome` dataclass serialization
- `StubProviders` health/reply behavior
- `_seed_eval_root` idempotency
- File:line scoring integration

**Fix:** Add `tests/test_reply_builder.py` with pytest.

**Severity:** MEDIUM — critical eval infrastructure with no tests.

---

## MEDIUM Issues

### 10. `answer_first` Failure — gemini Provider Opens with Deferral
**File:** `reviews/WEBBOB-EVALS-0927.json` (eval data, not code)

Case start-01: `"Okay, I'll focus on getting all the projects..."` instead of `"Running X jobs..."`

**Fix:** This is a prompt/instruction issue to the LLM, not code. The `reply_builder` should inject system prompt modification or the `state`/`dispatcher` providers should intercept.

**Severity:** MEDIUM — quality requirement (answer-first replies) violated.

---

### 11. `no_empty_promises` Failures — Hollow Progress
**File:** `reviews/WEBBOB-EVALS-0927.json`

Cases start-01, criticism-02: Responses like `"I'll focus on..."` without actual job creation.

**Fix:** Ensure dispatcher/provider validates that responses claiming action actually contain job IDs.

**Severity:** MEDIUM — user experience broken (false expectations).

---

### 12. Race Condition: Global State in `reply_builder.py`
**File:** `webchat/reply_builder.py`

The `_seed_eval_root` uses module-level state without locking:
```python
def _seed_eval_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    # ... modifies shared state
```

**Fix:** Add threading lock or make function stateless.

**Severity:** LOW — single-threaded usage likely, but eval harness may parallelize.

---

### 13. No Error Handling in Session File Loop
**File:** `webchat/mine_reply_eval_cases.py:130-140`
```python
for path in sorted(session_dir().glob("*.json")):
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        continue  # Silent failure
```
**Issue:** Silently skips corrupt files. Could hide data pipeline issues.

**Fix:** Log warning:
```python
import logging
logger = logging.getLogger(__name__)
# ...
except (OSError, json.JSONDecodeError) as e:
    logger.warning(f"Skipping corrupt session {path}: {e}")
    continue
```

**Severity:** LOW — mostly cosmetic.

---

## Missing Requirements (From Eval Goal)

Based on the stated goal: *"honest status naming every worker+task, plain-language job starts, short answer-first replies, texting draft->separate yes->send, voice barge-in, media on iPhone"*

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Honest status naming | PARTIAL | status_max_lines violated, but names appear correct |
| Plain-language job starts | FAIL | action_creates_jobs fails 5/41 cases |
| Short answer-first replies | FAIL | 14 status_max_lines failures |
| Texting draft->separate yes->send | PASS | text-01, text-02 passing |
| Voice barge-in | NOT TESTED | No eval cases |
| Media on iPhone | NOT TESTED | No eval cases |

**Fix:** Add eval cases for voice barge-in and media. Fix dispatcher for action_creates_jobs.

---

## VERDICT: **FAIL**

**Rationale:**
1. **14/41 eval cases failing** (34% failure rate) — primarily `status_max_lines` and `action_creates_jobs`
2. **Code bug in `rubrics_for()`** — unreachable return statement, missing else clause
3. **Core dispatcher bug** — not creating server-confirmed jobs for start prompts
4. **Status line limit enforcement missing** — functional gap in state provider
5. **Missing test coverage** for new eval infrastructure

**Required to Pass:**
- [ ] Fix `rubrics_for()` unreachable return
- [ ] Implement status line limiting (max 8 lines)
- [ ] Fix dispatcher to create server-confirmed jobs for start prompts
- [ ] Add unit tests for `reply_builder.py`
- [ ] Address `answer_first` and `no_empty_promises` failuresine_reply_eval_cases.py:18` | Debug patterns in SKIP | Test contamination |
| MEDIUM | `mine_reply_eval_cases.py:107` | Typo mining duplicates risk | Inconsistent case counts |
| LOW | `reply_builder.py:56` | Dead `as_meta()` code | Maintainability |
| LOW | Both new files | Missing unit tests | Regression risk |

---

## VERDICT: **FAIL**

**Rationale**: The `webchat/reply_builder.py` stub fundamentally does not implement the behaviors being evaluated. The `StubProviders` class returns empty health, hardcoded providers, and never creates jobs—all of which are the core behaviors the evals test for. This means the 24/41 passing score is **artificially inflated**: the failures are not catching real code bugs but rather the intentional stub behavior. The branch cannot match Bob the Bot without:

1. Implementing actual job queue integration in eval mode
2. Truncating status replies to ≤8 lines
3. Validating `answer_first` behavior
4. Adding missing unit/integration tests
5. Fixing the hardcoded provider assumptions

**Required Before Merge**:
- Rewrite `StubProviders` to reflect real server behavior
- Add `status_max_lines` truncation logic
- Add job creation tracking for `dispatcher`/`state` providers
- Add 2+ unit tests per new file
- Remove hardcoded `baseline_sha` or make dynamic
# Web Bob Code Review — bob-brain/draft/webbob-replies-1720 @ dff84e3

## Critical Security Issues

### 1. `services/draft_publish.py:63` — Command Injection via Unsanitized Branch Name
**Severity: CRITICAL**
The `branch` parameter passed to `gh pr list --head` is not sanitized. While `branch = "draft/" + row["id"]` from `dispatch_worker.py`, the `row["id"]` originates from task queue and could contain shell metacharacters if queue identifiers are malformed.

```python
# CURRENT (vulnerable)
return json.loads(gh("pr", "list", "--repo", remote, "--head", branch, "--state", "open",
                     "--json", "url,isDraft,headRefOid"))
```

**Fix:**
```python
BRANCH_SAFE = re.compile(r'^[a-zA-Z0-9._/-]+$')
def ensure_draft_pr(row, cwd, folder, remote, branch, sha):
    if not BRANCH_SAFE.match(branch):
        raise ValueError("Branch name contains unsafe characters: " + branch[:100})
    # ... rest unchanged
```

---

### 2. `services/dispatch_worker.py:153` — Path Injection via Unvalidated `cwd`
**Severity: HIGH**
The `cwd` from `task_repository(prompt)` is passed directly to `ask(cwd=cwd)` and `draft_publish.publish(row, cwd, ...)`. While `prompt` matching uses word boundaries (`\b`), crafted prompts could still trigger unintended repository selection or path traversal via symlinks.

```python
# CURRENT (risky)
cwd = task_repository(prompt)[1]  # from user-visible prompt
answer = redact(mini_worker.execute(row) if row["worker"] == "mini" else ask(row["worker"], prompt, cwd=cwd, ...
publication = draft_publish.publish(row, cwd, folder, project_catalog())
```

**Fix:**
```python
def execute(identifier, token):
    # ...
    repo = task_repository(prompt)[1]
    # Validate repo is under an approved root
    ALLOWED_ROOTS = [CONDUCTOR, Path.home() / "Documents"]
    if not any(repo.is_relative_to(root) for root in ALLOWED_ROOTS):
        repo = CONDUCTOR  # fallback to safe default
    cwd = repo
```

---

## High Priority Bugs

### 3. `webchat/chat_intent.py:15-16` — Fantasy Football Pattern Mismatch with Normalization
**Severity: HIGH**
`normalize_projects()` strips hyphens, but `PROJECT` regex still expects hyphens in fantasy football patterns. The regex uses `(?:storyland[ -])?` but `normalize_projects` converts input to `"storylandfantasyfootball"` (no hyphen).

```python
# Line 11 — regex expects hyphen/space
PROJECT = re.compile(r"\b(?:web\s*bob|...|(?:storyland[ -])?fantasy[ -]football|shelf)\b", re.I)

# Line 25 — strips hyphen before regex match
def projects(text):
    return list(dict.fromkeys(PROJECT_NAMES[re.sub(r"[\s-]+", "", match[0].lower())]
                              for match in PROJECT.finditer(normalize_projects(text))))  # BUG: normalize before regex but regex expects original
```

**Fix:**
```python
def projects(text):
    normalized = normalize_projects(text)
    return list(dict.fromkeys(PROJECT_NAMES[re.sub(r"[\s-]+", "", match[0].lower())]
                              for match in PROJECT.finditer(normalized)))  # Use normalized consistently
```

---

### 4. `webchat/live_replies_check.py:47` — Fragile Hardcoded Time Assertion
**Severity: MEDIUM**
The assertion `require("6:20" not in codex, ...)` is brittle and tied to specific Claude reset timing that changes with timezone/season.

```python
# CURRENT (fragile)
require("6:20" not in codex, "Claude reset time attached to Codex")
```

**Fix:**
```python
# Check that reset time is not misattributed to wrong LLM
RESET_TIME = re.compile(r'\d{1,2}:\d{2}\s*(?:am|pm)', re.I)
if RESET_TIME.search(codex):
    require("Claude" not in codex or "reset" not in codex.lower(),
            "Reset time misattributed to Codex")
```

---

### 5. `services/test_dispatch.py:386` — Conditional Test Assertion Skips Validation
**Severity: MEDIUM**
The assertion `self.assertEqual(ask.call_count, 3 if review == "Not JSON" else 2)` only validates call count for one specific review value. Other review formats are not checked.

```python
# CURRENT (incomplete)
for review in ("Not JSON", '{"accepted": true, "reason": "Good"}', '{"accepted": false}'):
    # ... setup code ...
    self.assertEqual(ask.call_count, 3 if review == "Not JSON" else 2)  # Only validates one branch
```

**Fix:**
```python
self.assertEqual(ask.call_count, 3 if review == "Not JSON" else 2)
if review != "Not JSON":
    self.assertEqual(ask.call_count, 2)  # Explicit validation for non-error case
```

---

## Medium Priority Issues

### 6. `webchat/chat_intent.py:14` — Inconsistent Fantasy Football in Regex Variants
**Severity: MEDIUM**
`PROJECT` includes Fantasy Football variants, but `RELEASE` and `PUSH` do not fully reflect this.

```python
# PROJECT includes fantasy variants
PROJECT = re.compile(r"\b(?:...|(?:storyland[ -])?fantasy[ -]football|...)\b", re.I)

# RELEASE may not match "go ahead on Fantasy Football"
RELEASE = re.compile(r"^(?:go(?:\s+ahead)?|resume)(?=$|[.!,:]|\s+...)\b", re.I)  # Missing fantasy football
```

**Fix:** Update `RELEASE` and `PUSH` to include fantasy football patterns consistently.

---

### 7. `webchat/reply_authority.py:72-73` — Potential KeyError on Malformed Row
**Severity: LOW**
`_work_line()` accesses `row["state"]` directly without `.get()`, which could raise `KeyError` for malformed rows.

```python
# Line 80
state = {"running": "running for ", ...}[row["state"]]  # KeyError if unexpected state
```

**Fix:**
```python
KNOWN_STATES = {"running": "running for ", "paused": "paused; process age ",
                "claimed": "claimed; execution unconfirmed; age ",
                "unverified": "session open; worker activity unconfirmed; age "}
state = KNOWN_STATES.get(row["state"], "unknown state; age ")
```

---

## Missing Tests

### 8. No test for `normalize_projects()` typo correction edge cases
**Location:** `webchat/test_chat_intent.py` — add test for single-char typos, multi-word typos, hyphenated names.

### 9. No test for `ensure_draft_pr` with malicious branch names
**Location:** `services/test_draft_publish.py` — add test for branch names with `;`, `|`, `--` to verify sanitization.

### 10. No integration test for `project_start()` with mixed project/normal requests
**Location:** `webchat/test_chat_intent.py` — verify "start WebJam" vs "I want to start working on WebJam" route correctly.

---

## Summary Table

| Priority | File:Line | Issue | Type |
|----------|-----------|-------|------|
| CRITICAL | `draft_publish.py:63` | Command injection via branch | Security |
| HIGH | `dispatch_worker.py:153` | Path injection via cwd | Security |
| HIGH | `chat_intent.py:15-16` | Fantasy football pattern mismatch | Bug |
| MEDIUM | `live_replies_check.py:47` | Hardcoded time assertion | Fragility |
| MEDIUM | `test_dispatch.py:386` | Skipped test validation | Test Gap |
| MEDIUM | `chat_intent.py:14` | Inconsistent regex variants | Consistency |
| LOW | `reply_authority.py:72-73` | KeyError on malformed row | Robustness |

---

## VERDICT: FAIL

**Reason:** Critical command injection vulnerability in `draft_publish.py:ensure_draft_pr()` allows unsanitized input to reach shell commands. High-severity path injection risk in `dispatch_worker.py` passes user-influenced `cwd` to external functions. Functional bug in `chat_intent.py` prevents Fantasy Football project matching due to normalization/regex mismatch.

**Required before merge:**
1. Sanitize branch name with regex whitelist before `gh` calls
2. Validate `cwd` is under allowed roots before passing to external functions  
3. Fix `projects()` to use normalized text consistently
4. Add tests for injection attempts blocked by sanitizationctness
**File:** `webchat/live_replies_check.py:59`

```python
_, replay = client.submit(cid, exchange["message"], answer["request_id"])
require(replay["task_ids"] == ids, "Replay created duplicate jobs")
```

**Issue:** Test only checks `task_ids` equality but doesn't verify the second response content is identical to the first (which would prove idempotency). The variable `_` discards the first response.

**Fix:** Store first response and compare both content and task IDs.

---

### 14. `test_live_replies_check.py` Doesn't Test Redaction
**File:** `webchat/test_live_replies_check.py`

**Issue:** Test asserts `self.assertNotIn(self.chat.password, output.read_text())` but never writes sensitive data to `output`. Test is vacuous.

---

### 15. `test_draft_publish.py`—Overwrites `record["isDraft"]`
**File:** `services/test_draft_publish.py:28`

```python
record["isDraft"] = False  # This mutates the shared fixture
```

**Issue:** Test mutates a shared object. If test order changes or fixture is reused, behavior is unpredictable.

**Fix:** Copy the record before mutation.

---

## 🟢 LOW (Style/Improvements)

### 16. `project_catalog()` Called on Every `execute()`
**File:** `services/dispatch_worker.py:110`

**Issue:** `project_catalog()` reads and parses two JSON files on every task execution. For high-throughput scenarios, this is wasteful.

**Fix:** Cache result with `@lru_cache` or compute once at module load.

---

### 17. Inconsistent Status Reply Format
**File:** `webchat/reply_authority.py:104`

```python
lines.append(WORKER_NAMES[name] + ": " + current + _cooldown(snap, name) + ".")
```

**Issue:** Status replies now use `: ` delimiter (e.g., "Codex: idle.") instead of ` — ` (e.g., "Codex — idle."). This changes the established format without version bump or migration plan.

---

### 18. Hardcoded Project List in `task_queue.py`
**File:** `state/task_queue.py:172`

```python
if publish_project is not None and (kind != "coding" or publish_project not in ("WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football", "Shelf", "Web Bob")):
```

**Issue:** Hardcoded project names drift from `projects.json`. Adding a project requires editing multiple files.

**Fix:** Validate against `project_catalog()` keys at runtime.

---

## Missing Tests Summary

| Component | Missing Coverage |
|-----------|------------------|
| `normalize_projects()` | All misspellings, edge cases |
| `project_start()` | Empty projects, ALL_PROJECTS fallback |
| `correcting_status()` | Criticism without prior status |
| `ensure_draft_pr()` | Race condition, network failure |
| `deploy_replies.py` | Restart failure, rollback success |
| `test_live_replies_check.py` | Actual redaction of secrets |

---

## VERDICT: **FAIL**

### Blocking Issues (Must Fix Before Merge):
1. **Bug #3**: `cwd` used before assignment — `execute()` will crash at runtime
2. **Bug #4**: `correcting_status()` corrupts conversation state on every call
3. **Bug #2**: Path injection in `normalize_projects()` can corrupt user text
4. **Bug #5/#6**: `project_start()` can trigger without projects, breaking routing

### Recommended Fixes Before Retest:
- Fix `dispatch_worker.py:158` to define `cwd` before use
- Fix `reply_authority.py:156-163` to guard `pop()` inside `if CRITICISM`
- Add project name boundary check in `normalize_projects()` or restrict to project context
- Ensure `project_start()` returns `False` when no projects identified; handle in `enqueue_work()`
- Add `provider_health` to snapshot passed to `format_operational_reply()`
- Add missing unit tests for new functions
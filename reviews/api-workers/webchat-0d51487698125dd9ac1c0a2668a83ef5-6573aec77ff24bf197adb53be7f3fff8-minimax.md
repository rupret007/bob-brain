## Concrete Findings: Web Bob / Mini-Conductor System Review

### Limitation Acknowledged
The original task prompt for "Web Bob instinct 0810" was not recorded in the journal or state files. I cannot reconstruct its exact assignment. I will work from observable code and state only.

---

### Finding 1: `lanes.py` `slot()` Context Manager Has a Bug — Premature Lock Release

**File:** `services/lanes.py`, lines ~38-53

```python
@contextlib.contextmanager
def slot(lane):
    if lane not in ("gemini", "minimax"):
        with lock("lane-" + lane, blocking=False):
            yield
        return
    usage = budget.check(lane)
    limit = 1 if usage["tier"] == "slow" else task_queue.capacity(lane)
    with lock("lane-" + lane, blocking=False, shared=True):
        for index in range(limit):
            stack = contextlib.ExitStack()
            try:
                stack.enter_context(lock("lane-" + lane + "-" + str(index), blocking=False))
            except BlockingIOError:
                stack.close()   # ← BUG: releases ALL acquired locks in ExitStack
                continue
            with stack:         # ← This `with` only runs if we got a lock
                yield
            return               # ← Early return inside `with` block; ExitStack.__exit__ fires
```

**Problem:** When `BlockingIOError` is caught, `stack.close()` releases any locks already acquired by the `ExitStack` before the current iteration. But even on success, the `with stack:` block's `__exit__` fires `stack.close()` when the `yield` completes — meaning **the per-index locks are released before the caller finishes using the lane**, creating a race window where another caller can acquire the same slot.

**Fix:** Use nested explicit lock contexts instead of `ExitStack` for index slots:

```python
@contextlib.contextmanager
def slot(lane):
    if lane not in ("gemini", "minimax"):
        with lock("lane-" + lane, blocking=False):
            yield
        return
    budget.check(lane)
    limit = task_queue.capacity(lane)
    with lock("lane-" + lane, blocking=False, shared=True):
        for index in range(limit):
            try:
                inner = lock("lane-" + lane + "-" + str(index), blocking=False)
                inner.__enter__()
            except BlockingIOError:
                continue
            try:
                yield
            finally:
                inner.__exit__(None, None, None)
            return
        raise BlockingIOError("All API slots are occupied")
```

---

### Finding 2: `job_event()` Cannot Transition *to* `harvested` from Non-Launched State

**File:** `services/state.py`, lines ~88-107

```python
def job_event(job_id, state=None, **fields):
    if state and state not in ("queued", "launched", "running", "blocked", "harvested"):
        raise ValueError("invalid job state")
    ...
    row = dict(previous, **fields)
    row.update(job_id=job_id, state=state or previous.get("state", "launched"))
    if previous.get("state") == "harvested" and previous.get("outcome") != "blocked" and row["state"] != "harvested" and not fields.get("invalidate_result"):
        raise ValueError("cannot relaunch a harvested job: " + job_id)
```

**Problem:** The guard only blocks *relaunching* a harvested job. But there's no guard preventing a `blocked` job from going directly to `harvested` without ever reaching `running`. In `jobs.py` `recover()`, the flow allows:

```
running → worker exits → blocked() → harvest() if result exists
```

This means a job that crashes can be harvested as successful even if its result is incomplete. The `BLOCKER.txt` check in `recover()` runs, but only after the result-closeout logic has already fired.

**Fix:** Require `running` state to have been reached before a `harvested` outcome is recorded, unless `outcome=blocked` is explicit:

```python
if row["state"] == "harvested" and fields.get("outcome") != "blocked":
    if previous.get("state") not in ("running", "blocked") and not fields.get("invalidate_result"):
        raise ValueError("cannot harvest a job that never reached running: " + job_id)
```

---

### Finding 3: `dispatch_worker.py` Result Acceptance JSON Escape Issue

**File:** `services/dispatch_worker.py`, line ~240

```python
acceptance = json.loads(redact(json.dumps(acceptance)))
```

**Problem:** `redact()` operates on the JSON *string*, not the structured data. If the answer contains strings that *after* JSON serialization look like secrets (e.g., a base64-encoded key that matches a redaction pattern), they will be double-escaped or corrupted. For example, a result containing the text `sk-abc123` would be redacted in the string, then `json.loads` would parse it — but any redaction that adds `[secret removed]` could break JSON structural integrity if it appears inside a string value that spans lines.

**Impact:** Low in practice (the redact patterns are specific), but could cause `json.JSONDecodeError` in `result_acceptance.py` if the redacted text corrupts the JSON structure.

---

### Finding 4: No Maximum Bound on `reviewer_cycle()` Reviews Per Cycle

**File:** `services/runtime.py`, `reviewer_cycle()` function

```python
for record in candidates:
    ...
    for model in ("claude", "cursor", "minimax", "gemini"):
        outcomes[model] = critique(model, prompt, result.with_name(...))
    ...
    return  # ← correctly returns after one
```

The function correctly returns after one review per cycle. However, the `candidates` list is sorted by `review_attempt_at` ascending — meaning jobs that failed all reviews are retried before jobs that haven't been tried at all. This is backwards: a job with `review_attempt_at=0` (never tried) should be reviewed before one that has repeatedly failed.

**Fix:**

```python
candidates.sort(key=lambda r: (
    0 if r.get("review_attempt_at", 0) == 0 else 1,  # untried first
    r.get("review_attempt_at", 0),
    -r.get("launched_at", 0)
))
```

---

### Actionable Plan

1. **Fix `lanes.py` `slot()` lock release bug** — prevents lane slot collisions under load
2. **Add state guard in `job_event()`** — prevents harvesting jobs that never ran
3. **Sort reviewer candidates by untried-first** — improves review coverage
4. **Audit `redact()` interaction with JSON serialization** — potential corruption path

No deployment or conflict resolution required. These are local-only code observations.

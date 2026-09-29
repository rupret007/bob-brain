## Code Review: tip 953f4402b8049b877bcf6fd0bfd8b94e22aaae70

### 1. O(n) Trim Correctness

**Old code (O(n²)):**
- Computed `sum(len(entry) for entry in trimmed))` inside a `while` loop — O(n) per iteration
- Called `trimmed.pop(0)` which is O(n) for list front pops
- Total: O(n²)

**New code (O(n)):**
```python
sizes = [len(entry.encode("utf-8")) for entry in lines]  # O(n) once
total = sum(sizes)                                         # O(n) once
start = 0
while start < len(lines) and total > max_bytes:            # O(k) where k ≤ n
    total -= sizes[start]                                  # O(1)
    start += 1                                             # O(1)
return lines[start:]                                       # O(n) slicing
```
**Result: O(n) — correct.**

---

### 2. Byte Budget

The implementation uses `len(entry.encode("utf-8"))` to measure actual byte consumption. This is accurate for enforcing a byte budget. The algorithm correctly keeps the newest (end) lines while removing oldest (front) lines until under budget.

**Minor note:** The original implementation used `len(entry)` (character count). The new code changes to byte count — this is arguably a **more correct** interpretation of `PROFILE_MAX_BYTES`, but it is a behavioral change. Tests use ASCII data so this discrepancy is masked. However, byte-based budgeting is the right semantics for a file-size limit.

---

### 3. Lock Open/Acquire Error Context

```python
try:
    lock_file = lock_path.open("a")
except OSError as exc:
    raise OSError(f"Could not open profile lock file {lock_path}: {exc}") from exc
try:
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
    except OSError as exc:
        raise OSError(f"Could not acquire profile lock {lock_path}: {exc}") from exc
    # ... critical section ...
```

Both failure modes get descriptive `OSError` messages with path context and chained original exception. **Correct.**

---

### 4. No Lock Leaks

```python
try:                      # lock_file opened
    try:                  # flock acquired
        # write logic
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)   # always unlock
finally:
    lock_file.close()                            # always close
```

| Scenario | Unlock | Close |
|---|---|---|
| Write succeeds | ✓ (inner finally) | ✓ (outer finally) |
| Write fails | ✓ | ✓ |
| flock fails | N/A (not acquired) | ✓ (outer finally) |
| open fails | N/A (not opened) | N/A |

**No lock leaks. Correct.**

---

### 5. Tests Adequacy

| Test | Coverage | Assessment |
|---|---|---|
| `test_trim_profile_lines_keeps_newest_under_budget` | 5000 lines, exact budget match, verifies newest 100 kept | ✓ Strong |
| `test_trim_profile_lines_noop_when_under_budget` | 3 lines, generous budget | ✓ Basic edge |
| `test_append_profile_memory_lock_open_failure_raises_oserror` | Directory at lock path, verifies OSError with path in message | ✓ Correct |

Tests are adequate for the changed code. They directly test the fixed function and error path.

---

### Minor Observations (non-blocking)

1. **Behavioral shift (char → bytes):** `_trim_profile_lines` now measures UTF-8 bytes vs. characters. This is arguably more correct for a byte budget, but tests don't explicitly validate multi-byte scenarios. Low risk.

2. **No test for write failure during lock hold:** If `atomic_text` fails, the lock is released correctly but this path isn't explicitly tested. Acceptable as it's implicitly covered by the `finally` structure.

---

### Summary

| Requirement | Status |
|---|---|
| O(n) trim correctness | ✓ PASS |
| Byte budget enforcement | ✓ PASS |
| Lock error context | ✓ PASS |
| No lock leaks | ✓ PASS |
| Tests adequate | ✓ PASS |

VERDICT: PASS

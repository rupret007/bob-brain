## Strict Code Review: `draft/webbob-gaps-1725` (3a7a571)

### Scope
Durable memory write, web research, on-demand screenshots (per `GAPS-IMPL-0927.md`).

---

### 🔴 Critical: Missing Test Coverage

| File:Line | Issue | Severity |
|-----------|-------|----------|
| `webchat/test_bob_gaps.py` | No test for memory dismissal ("never mind", "cancel", "dismiss"). `bob_gaps_memory_turn` logic paths are untested. | High |
| `webchat/test_bob_gaps.py` | No test for stale memory proposal detection (wrong UUID in "yes, save memory proposal ..."). | High |
| `webchat/test_bob_gaps.py` | No test for `needs_web_search` negative cases (non-matching strings, empty string, >600 chars). | Medium |
| `webchat/test_bob_gaps.py` | No test for `MEMORY_CANCEL` and `MEMORY_CONFIRM_PROPOSAL` regexes directly. | Medium |
| `webchat/test_bob_gaps.py` | No test for `bob_gaps_memory_turn` with `provider != "auto"` (should return None). | Low |
| `webchat/test_bob_gaps.py` | No test for `try_bob_gaps` with ledger root mismatch (should return None). | Low |
| `webchat/test_bob_gaps.py` | No test for screenshot capture failure (permission denied, window not found). | Medium |
| `webchat/test_bob_gaps.py` | No test for web search failure (network error). `app.py:342` catches `URLError`, but not exercised. | Medium |
| `webchat/test_bob_gaps.py` | No test for `format_web_search_reply` with missing keys (KeyError protection missing). | Low |
| `webchat/test_bob_gaps.py` | No integration test for `/api/captures/<id>` endpoint. `Handler` route untested. | High |

**Fix:** Add tests for each missing case.

---

### 🟡 Medium: AppleScript String Injection / Error Handling

| File:Line | Issue |
|-----------|-------|
| `webchat/bob_gaps.py:83` | `_macos_window_id` inserts `app_name` directly into AppleScript string without escaping quotes or backslashes. Input `Calc"` generates invalid AppleScript `name contains "Calc""`, causing silent failure and misleading "window not found" error to user. |

**Fix:**
```python
# bob_gaps.py:79-89
def _macos_window_id(app_name: str) -> int | None:
    escaped_name = app_name.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        'tell application "System Events" to id of first window of '
        f'(first process whose name contains "{escaped_name}")'
    )
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return int(completed.stdout.strip())
    except ValueError:
        return None
```

---

### 🟢 Low: Defensive Coding

| File:Line | Issue |
|-----------|-------|
| `webchat/bob_gaps.py:153` | `format_web_search_reply` accesses `result["answer"]` and `result['heading']` directly. If called with dict missing keys, raises `KeyError`. Should use `.get()`. |

**Fix:**
```python
# bob_gaps.py:151-156
def format_web_search_reply(result: dict) -> str:
    lines = [result.get("answer", "")]
    if result.get("heading"):
        lines[0] = f"**{result['heading']}** — {lines[0]}"
    if result.get("source"):
        lines.append(f"Source: [{result['source']}]({result['source']})")
    return "\n\n".join(lines)
```

---

### 🟢 Low: Race Condition (Minor)

| File:Line | Issue |
|-----------|-------|
| `webchat/bob_gaps.py:70` | `append_profile_memory` has no file locking. Concurrent writes (unlikely in single-user webchat, but possible if multiple processes) could interleave. |

**Fix:** Add `fcntl.flock` (Linux/macOS) or acknowledge limitation. For single-user, not critical.

---

### ✅ Verified Correct

- `resolve_capture_path`: Regex `[0-9a-f]{16}` validation is correct, prevents path traversal.
- `public()`: Correctly filters `pending_memory` and `pending_memory_id` from client response.
- `bob_gaps_memory_turn`: Stale proposal check logic is sound.
- `try_bob_gaps`: Exception handling covers `OSError`, `URLError`, `JSONDecodeError`, `TimeoutError`.
- Screenshot/memory/web search integration order in `apply_turn` and `submit` is correct.
- Frontend `app.js` action card logic for memory matches backend `action_card` structure.
- `web_search` DuckDuckGo API usage is correct (no API key required, appropriate params).
- `MEMORY_CANCEL` alias `MEMORY_DISMISS` usage is consistent.
- Tests mock correct import paths (`app.web_search`, `app.capture_screenshot`).

---

### VERDICT: **FAIL**

**Reasons:**
1. **Missing test coverage** (Critical): Core logic paths (dismissal, stale proposal, failure modes) are untested. This violates the "honest status naming" goal (which implies verifiable behavior).
2. **AppleScript escaping bug** (Medium): User-provided app names with quotes cause silent failure with misleading error.
3. **Defensive coding gap** (Low): `format_web_search_reply` not robust to malformed input.

**Required before merge:** Fix AppleScript escaping and add missing tests. The low-priority items are acceptable as `TODO` if acknowledged.
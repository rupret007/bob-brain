This is a strict code review of branch `draft/webbob-gaps-1725` at commit `70d59e3`.

The changes introduce three new features to align Web Bob with "Bob the Bot": durable memory, web research, and on-demand screenshots. The implementation is high-quality, with a strong focus on security, robustness, and comprehensive testing. The code successfully meets the stated goals.

However, a strict review identified a few minor bugs and areas for improvement.

### Ranked Bug Report

#### 1. Medium: Missing Ledger Record on Memory Save Failure

*   **File**: `webchat/app.py:91`
*   **Bug**: In `bob_gaps_memory_turn()`, the `except OSError` block handles file write errors by showing a message to the user but fails to record this failed turn in the application's ledgers (`record_turn` and `state_ledger.record_webchat_turn`). This leads to an incomplete audit trail, as failed interactions are silently dropped from the history.
*   **Fix**: Add calls to `self.record_turn` and `state_ledger.record_webchat_turn` within the `except` block to ensure that failed memory save attempts are logged, just as successful ones are.

    ```python
    # webchat/app.py:91
    except OSError as exc:
        conversation["pending_memory"] = pending_memory
        # ... (update message content) ...
        self.save(conversation)
        self.conversations[identifier] = conversation
        # Add these lines:
        self.record_turn(conversation_id=identifier, ask=text, provider="state", jobs=[], files=[],
                    commits=[], confirmations=[], refusals=[f"Failed memory save: {pending_memory[:100]}"], 
                    open_items=[], request_id=request_id)
        state_ledger.record_webchat_turn(ledger, ask=text, provider="state", request_id=request_id)
        return self.public(conversation)
    ```

#### 2. Low: Inefficient Profile Trimming & Inconsistent Sizing

*   **File**: `webchat/bob_gaps.py:64`
*   **Bug**: The function `_trim_profile_lines` uses a `while` loop that repeatedly calls `sum(len(entry) for entry in trimmed)`, resulting in quadratic complexity `O(N*M)` where N is lines to remove and M is total lines. For a large profile needing significant trimming, this could be slow. Additionally, this code counts *characters*, but the associated test (`test_append_profile_memory_trims_when_oversized`) asserts against *bytes*, creating an inconsistency that could lead to unexpected behavior with multi-byte characters.
*   **Fix**: Refactor the function to iterate only once, calculating total bytes and removing lines from the beginning until the size is under the limit. This improves efficiency to `O(M)` and correctly uses byte counts.

    ```python
    # webchat/bob_gaps.py:62
    def _trim_profile_lines(lines: list[str], max_bytes: int = PROFILE_MAX_BYTES) -> list[str]:
        byte_lines = [line.encode('utf-8') for line in lines]
        total_bytes = sum(len(b) for b in byte_lines)
    
        if total_bytes <= max_bytes:
            return lines
    
        start_index = 0
        while start_index < len(byte_lines) and total_bytes > max_bytes:
            total_bytes -= len(byte_lines[start_index])
            start_index += 1
        
        return lines[start_index:]
    ```

#### 3. Low: Missing Test for Age-Based Screenshot Pruning

*   **File**: `webchat/test_bob_gaps.py`
*   **Missing Test**: The test suite for `_prune_captures` includes a test for limiting the total *count* of screenshots (`test_prune_captures_enforces_max_count`) but lacks a test case for pruning files based on their *age*. This leaves a branch of the cleanup logic untested.
*   **Fix**: Add a new test to verify that files older than `max_age_days` are correctly deleted, even if the total count is below the maximum.

    ```python
    # In webchat/test_bob_gaps.py, within UnitTests or a relevant class
    def test_prune_captures_enforces_max_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "old.png"
            path.write_bytes(b"png")
            # Set mtime to 10 days ago
            ten_days_ago = time.time() - (10 * 24 * 60 * 60)
            os.utime(path, (ten_days_ago, ten_days_ago))
            
            # Prune files older than 7 days (the default)
            _prune_captures(folder, max_count=100)
            self.assertFalse(path.exists())
    ```

---
### Security Review

The security posture of this change is excellent.
*   **Path Traversal**: Prevented by strict hex-string validation on capture IDs (`webchat/bob_gaps.py:228`).
*   **Command Injection**: Prevented by passing arguments as a list to `subprocess.run` and by correctly escaping user input for the `osascript` call. An explicit security test (`test_macos_window_id_escapes_injection_payload`) validates the AppleScript escaping.
*   **Race Conditions**: Handled correctly for concurrent memory writes using `fcntl.flock`, which is verified with a threading-based test.

No security vulnerabilities were found.

---

### VERDICT: PASS

This is a high-quality contribution that meets its goals effectively. The implementation is robust, secure, and thoroughly tested. The few issues identified are minor, non-critical, and do not warrant failing the review. The fixes are recommended before merging.
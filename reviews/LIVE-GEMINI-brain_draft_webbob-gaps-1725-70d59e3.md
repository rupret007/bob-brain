This is a strict code review for branch `brain/draft/webbob-gaps-1725` at commit `70d59e3`.

The changes introduce three significant features to bring Web Bob's capabilities closer to Bob the Bot: durable memory, web research, and on-demand screenshots. The implementation is robust, secure, and thoroughly tested.

### Review

#### High-Level Summary
The overall quality of the code is exceptional. Security considerations like command injection, path traversal, and resource exhaustion have been proactively addressed and tested. The use of file locking for concurrent memory writes (`fcntl`) and cryptographically secure tokens (`secrets`) demonstrates a high level of engineering discipline. The new features are well-integrated into the existing application flow, and the test suite is comprehensive.

The implementation successfully achieves its stated goals:
*   **Plain-language job starts:** The UI for memory confirmation (`Save memory` button) is a significant improvement.
*   **Short answer-first replies:** The web search feature is designed to provide direct answers.
*   **Draft->confirm->send pattern:** The "remember that" feature perfectly implements this two-step confirmation flow.
*   **Media support:** Displaying screenshots is a foundational step towards richer media interaction.

#### Bugs & Security Issues (Ranked)

No critical or high-severity bugs or security vulnerabilities were found. The following are minor issues.

1.  **BUG (Minor):** The profile size trimming logic counts characters instead of bytes. With multi-byte UTF-8 characters, this could cause the `profile.md` file to slightly exceed its intended `PROFILE_MAX_BYTES` limit.
    *   **File:** `webchat/bob_gaps.py:73`
    *   **Line:** `while trimmed and sum(len(entry) for entry in trimmed) > max_bytes:`
    *   **Fix:** To be more precise, the length should be calculated based on the byte representation.
        ```python
        # old
        while trimmed and sum(len(entry) for entry in trimmed) > max_bytes:
        # new
        while trimmed and sum(len(entry.encode("utf-8")) for entry in trimmed) > max_bytes:
        ```
    *   **Impact:** Low. The potential size overage is small and unlikely to cause operational issues.

2.  **SECURITY (None Found):** The code demonstrates excellent security posture.
    *   **Path Traversal:** Prevented in the `/api/captures/` endpoint by strictly validating the `capture_id` with a regex (`webchat/bob_gaps.py:226`).
    *   **Command Injection:** Prevented in the screenshot feature by properly escaping the application name before its use in AppleScript (`webchat/bob_gaps.py:126`) and validating other inputs. This is explicitly covered by a security test.
    *   **Resource Exhaustion:** Both screenshot captures and profile memory are pruned/trimmed to prevent unbounded growth, mitigating denial-of-service risks.

#### Missing Tests (Ranked)

The test coverage is extensive and of high quality. The following is a minor gap.

1.  **MISSING TEST (Minor):** The screenshot pruning logic in `_prune_captures` is tested for its max-count enforcement but lacks a specific test case for its max-age enforcement. The code is simple and likely correct, but a dedicated test would ensure it behaves as expected.
    *   **File:** `webchat/test_bob_gaps.py`
    *   **Suggestion:** Add a test to the `UnitTests` class that creates several capture files, uses `os.utime` to artificially age some of them beyond the `max_age_days` limit, calls `_prune_captures`, and asserts that only the old files were deleted.

### Verdict

The submitted code is of excellent quality. It successfully implements the desired features with a strong focus on robustness, security, and testability. The minor issues identified are non-critical and do not detract from the overall strength of the implementation.

**VERDICT: PASS**
This is a strict code review of branch `brain/draft/webbob-gaps-1725` at commit `9242839`. The goal is to implement durable memory, web research, and on-demand screenshots to improve feature parity with "Bob the Bot".

The review found the code to be of exceptionally high quality, with robust error handling, proactive security mitigations, and comprehensive test coverage.

### Bugs and Security Vulnerabilities

#### 1. (Minor Bug) Ambiguous Window Targeting for Screenshots

*   **File:** `webchat/bob_gaps.py:91`
*   **Ranking:** Bug, Minor
*   **Description:** The AppleScript in `_macos_window_id` uses `whose name contains "{escaped_name}"` to find the target application process. This can lead to ambiguity. For example, if the user asks for a screenshot of "Notes" and both "Notes" and "Stickies Notes" are running, the function might capture a window from the wrong application depending on which process is listed first by "System Events".
*   **Fix:** For more precise targeting, change the filter from `contains` to `is`. This creates a stricter match, reducing ambiguity. While this removes the flexibility of partial matches (e.g., "Calculator" for "Calculator.app"), it makes the behavior more predictable.

    ```python
    # webchat/bob_gaps.py:91
    # Original:
    script = (
        'tell application "System Events" to id of first window of '
        f'(first process whose name contains "{escaped_name}")'
    )
    # Proposed Fix:
    script = (
        'tell application "System Events" to id of first window of '
        f'(first process whose name is "{escaped_name}")'
    )
    ```

### Security Analysis (No vulnerabilities found)

The code demonstrates excellent security posture. Potential high-impact vulnerabilities were proactively identified and mitigated:

1.  **Path Traversal:** The `/api/captures/<id>` endpoint is secured against path traversal. The `resolve_capture_path` function in `bob_gaps.py` validates the `capture_id` with a strict regex (`r"[0-9a-f]{16}"`) before constructing a file path. This is the correct way to handle user-provided filenames.
2.  **Command Injection (AppleScript):** User input for the screenshot target application is correctly escaped in `_macos_window_id` before being interpolated into the AppleScript string. The `_escape_applescript_string` function neutralizes quote and backslash characters, and this mitigation is validated by a dedicated security test (`test_macos_window_id_escapes_injection_payload`).
3.  **Command Injection (Shell):** The `screencapture` and `osascript` commands are executed using a list of arguments passed to `subprocess.run`, which completely avoids shell injection vulnerabilities.

### Missing Tests (No significant gaps found)

Test coverage is excellent and a major strength of this change. The new `test_bob_gaps.py` file includes:
*   Unit tests for individual parsers, regexes, and helper functions.
*   End-to-end acceptance tests for the primary success and failure modes of all three new features.
*   A dedicated security test for the AppleScript injection mitigation.
*   A live-server integration test for the new `/api/captures/` API endpoint.

This level of testing provides high confidence in the correctness and security of the implementation.

### VERDICT: PASS

This change is an exemplary implementation of the specified features. It is well-structured, robust, secure, and thoroughly tested. The minor bug identified is a design trade-off and does not compromise the stability or security of the system. The branch successfully achieves its goals and is approved for merge.
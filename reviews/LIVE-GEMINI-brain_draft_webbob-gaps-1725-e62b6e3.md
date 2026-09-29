This is a strict code review of the Web Bob branch `brain/draft/webbob-gaps-1725` at commit `e62b6e3`.

The goal is to implement features to match "Bob the Bot", specifically durable memory, web research, and on-demand screenshots.

### Review Summary

The branch successfully implements the three targeted features. The code is generally well-structured, includes a comprehensive test suite for the new functionality, and considers security implications for file system access and subprocess execution. However, a few issues in error handling, state management, and test coverage prevent it from passing a strict review.

### Bugs / Security / Missing Tests (Ranked by Severity)

1.  **Bug (Medium)**: `webchat/app.py:73`
    *   **Issue**: In `bob_gaps_memory_turn`, if a user confirms a stale memory proposal, an error message is sent, but the current `pending_memory` state is not cleared. If the user then sends a generic confirmation like "yes, save memory", it will save the newer, unconfirmed memory, which is an inconsistent and potentially surprising behavior.
    *   **Fix**: After sending the "Stale memory proposal" message, clear the pending state to force the user to start the process again. Add the following lines after line 76 (`self.save(conversation)`):
        ```python
        conversation.pop("pending_memory", None)
        conversation.pop("pending_memory_id", None)
        ```

2.  **Security (Low)**: `webchat/app.py:131`, `webchat/app.py:139`
    *   **Issue**: Raw exception messages from `capture_screenshot` and `web_search` are sent directly to the chat client. This can leak potentially sensitive system information, such as command-line tool error output, file paths, or network error details.
    *   **Fix**: Replace `content=str(exc)` with a generic, user-friendly error message. Log the full exception server-side for debugging.
        *   At `webchat/app.py:131`, change to:
            ```python
            content="I was unable to take a screenshot. An internal error occurred."
            ```
        *   At `webchat/app.py:139`, change `reply = ...` to:
            ```python
            reply = "I could not complete a web search right now. An internal error occurred."
            ```

3.  **Missing Test (Medium)**: `webchat/test_bob_gaps.py`
    *   **Issue**: The test suite lacks an integration-level test to verify that the AppleScript string escaping for screenshot targets prevents command injection. While a unit test exists (`test_macos_window_id_escapes_injection_payload`), an integration test using `self.submit()` would provide stronger assurance that the end-to-end flow is secure.
    *   **Fix**: Add a new test method to `ScreenshotGapTests` that attempts to take a screenshot of a maliciously crafted application name (e.g., `Finder" & do shell script "touch /tmp/pwned" & "`) and asserts that the mock `subprocess.run` call for `osascript` receives a correctly escaped, non-executable script string.

4.  **Missing Test (Low)**: `webchat/test_bob_gaps.py`
    *   **Issue**: The behavior where a pending memory is implicitly cancelled by an unrelated user message is implemented but not covered by a test. This is an important part of the memory feature's state machine.
    *   **Fix**: Add a test to `MemoryGapTests` that first triggers a memory confirmation prompt, then sends a non-confirm/non-cancel message (e.g., "hello world"), and finally asserts that `pending_memory` has been removed from the conversation state.

### VERDICT: FAIL

The implementation is strong and very close to complete. The features are well-designed and the test suite is comprehensive. However, the state management bug and the information leak via error messages are notable flaws. For a change of this nature, especially one involving interaction with the shell and file system, a higher bar for correctness and security is required. The branch should be updated to address the identified issues before being merged.
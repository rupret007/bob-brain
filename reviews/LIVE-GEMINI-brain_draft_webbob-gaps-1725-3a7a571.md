This is a strict code review for branch `brain/draft/webbob-gaps-1725` at commit `3a7a571`.

The branch successfully implements three major features from the gap audit: durable memory, web research, and on-demand screenshots. The implementation shows thoughtful design, particularly in the multi-turn memory confirmation flow and robust error handling in `webchat/app.py`. The frontend and testing additions are substantial.

However, the review has identified a critical security vulnerability and several medium-severity bugs that must be addressed.

### Bugs, Security, and Missing Tests (Ranked by Severity)

1.  **CRITICAL (Security): Command Injection**
    *   **File:** `webchat/bob_gaps.py:84`
    *   **Issue:** The `_macos_window_id` function directly embeds the `app_name` parameter into an AppleScript string without sanitization. A malicious user could provide a crafted `app_name` (e.g., `Finder" & do shell script "touch /tmp/pwned" & "`) to execute arbitrary shell commands on the host machine.
    *   **Fix:** Escape double quotes within the `app_name` string before interpolating it into the script.
        ```python
        # webchat/bob_gaps.py:82
        def _macos_window_id(app_name: str) -> int | None:
            safe_app_name = app_name.replace('"', '\\"')
            script = (
                'tell application "System Events" to id of first window of '
                f'(first process whose name contains "{safe_app_name}")'
            )
            # ... rest of the function
        ```

2.  **HIGH (Missing Tests): No Security Test for Injection**
    *   **File:** `webchat/test_bob_gaps.py`
    *   **Issue:** There is no test case to verify that the command injection vulnerability (item #1) is prevented. Security-critical code must be accompanied by tests that prove its correctness against malicious input.
    *   **Fix:** Add a test that attempts injection and asserts that no command is executed and the function fails gracefully (e.g., returns `None`). This would involve mocking `subprocess.run` and inspecting the command it was called with.

3.  **MEDIUM (Bug): macOS-Specific Code Without Platform Checks**
    *   **File:** `webchat/bob_gaps.py:80`, `webchat/bob_gaps.py:108`
    *   **Issue:** The screenshot functionality relies on macOS-specific tools (`screencapture`, `osascript`). The code does not check the operating system, and will crash with a `FileNotFoundError` if run on Linux or Windows. While `app.py` catches the resulting `OSError`, the user receives a generic error instead of a clear message.
    *   **Fix:** Check `sys.platform` at the start of `_macos_window_id` and `capture_screenshot` and raise a `RuntimeError` with an informative message if the OS is not macOS (`"darwin"`).
        ```python
        # webchat/bob_gaps.py (at top)
        import sys
        
        # In capture_screenshot and _macos_window_id
        if sys.platform != "darwin":
            raise RuntimeError("The screenshot feature is only available on macOS.")
        ```

4.  **MEDIUM (Missing Tests): No Error-Handling Tests**
    *   **File:** `webchat/test_bob_gaps.py`
    *   **Issue:** The tests only cover the "happy path." There are no tests to verify that the user receives a proper error message in chat if `web_search` fails (e.g., network error) or `capture_screenshot` fails (e.g., window not found).
    *   **Fix:** Add tests that use `patch` to make the underlying functions raise exceptions, then assert that the final chat message content contains the expected error text.

5.  **MEDIUM (Missing Tests): No Test for Stale Memory Confirmation**
    *   **File:** `webchat/test_bob_gaps.py`
    *   **Issue:** The logic in `app.py:53` to detect and reject stale memory confirmation buttons is a key feature for preventing race conditions but is not covered by any test.
    *   **Fix:** Add a test case that initiates a memory save, then initiates a second one, and then tries to confirm the first one, asserting that it is rejected with the "stale" message.

6.  **LOW (Bug): Lost Error Details from `screencapture`**
    *   **File:** `webchat/bob_gaps.py:112`
    *   **Issue:** The `subprocess.run` call for `screencapture` does not capture `stderr`. If the command fails for a specific reason, that diagnostic information is lost, making debugging difficult.
    *   **Fix:** Add `capture_output=True` and `text=True` to the `subprocess.run` call. If an exception occurs, include the contents of `stderr` in the error message.

7.  **LOW (Bug): Missing User-Agent in Web Search**
    *   **File:** `webchat/bob_gaps.py:136`
    *   **Issue:** The `web_search` function makes an API request to DuckDuckGo without setting a `User-Agent` header. This is against best practices and may lead to the request being blocked or rate-limited.
    *   **Fix:** Create a `urllib.request.Request` object, add a `User-Agent` header, and pass it to the opener.
        ```python
        # webchat/bob_gaps.py:135
        def web_search(query: str, opener=urllib.request.urlopen) -> dict:
            # ...
            req = urllib.request.Request(
                url, headers={"User-Agent": "WebBob-Bot/1.0 (https://github.com/example/repo)"}
            )
            with opener(req, timeout=20) as response:
                # ...
        ```

### VERDICT: FAIL

The presence of a critical command injection vulnerability requires an immediate FAIL verdict. While the features are well-implemented on the surface, this security flaw is unacceptable. The code cannot be approved until this and the other high/medium severity issues—particularly the missing tests for security and error handling—are resolved.
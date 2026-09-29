A strict code review of branch `draft/webbob-gaps-1725` follows.

### Review Summary

The branch successfully implements the three targeted features from the gap audit: durable memory, web research, and on-demand screenshots. The code is well-structured, includes comprehensive tests for new functionality, and correctly handles several critical security concerns, notably command injection in the screenshot feature and path traversal for serving captured images.

However, the review identifies a medium-severity operational bug and a low-severity bug related to error handling that prevent a `PASS` verdict under strict criteria.

### Bugs, Security, and Missing Tests (Ranked)

#### 1. (Medium) Bug: Uncontrolled File Growth Leading to Potential DoS

-   **File:** `webchat/bob_gaps.py` (functions `append_profile_memory`, `capture_screenshot`)
-   **Line:** `60`, `113`
-   **Description:** Both the memory and screenshot features write files to disk (`bob-brain/memory/profile.md` and `conductor/webchat/captures/*.png`) without any mechanism for size limiting, rotation, or cleanup. Over time, this will lead to unbounded disk usage, which can cause a denial-of-service condition by exhausting disk space on the host machine. This is a significant operational risk for any long-running service.
-   **Fix:** Implement a cleanup and limiting strategy. For screenshots, which are ephemeral, prune old files before creating a new one.
    ```python
    # In webchat/bob_gaps.py, add to imports
    import time

    # In webchat/bob_gaps.py, before capture_screenshot
    def _prune_captures(folder: Path, max_count: int = 100, max_age_days: int = 7):
        """Deletes old screenshot captures to prevent disk exhaustion."""
        try:
            now = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            
            # Use a single pass for efficiency
            captures = [p for p in folder.glob("*.png") if p.is_file()]
            captures.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # Prune by count first, then by age
            to_delete = set(captures[max_count:])
            for path in captures:
                if now - path.stat().st_mtime > max_age_seconds:
                    to_delete.add(path)
            
            for path in to_delete:
                path.unlink()
        except OSError:
            # Log this, but don't let cleanup failure block the main feature.
            pass

    # In webchat/bob_gaps.py, inside capture_screenshot
    def capture_screenshot(root: Path, target: str | None = None) -> tuple[str, Path]:
        if sys.platform != "darwin":
            raise RuntimeError("The screenshot feature is only available on macOS.")
        folder = root / "conductor/webchat/captures"
        folder.mkdir(parents=True, exist_ok=True)
        _prune_captures(folder) # Add this call
        capture_id = secrets.token_hex(8)
        # ... rest of the function
    ```

#### 2. (Low) Bug / Missing Test: Unhandled Exception on Memory File Write Failure

-   **File:** `webchat/app.py`
-   **Line:** `86`
-   **Description:** The call `append_profile_memory(self.root, pending_memory)` can raise an `OSError` if the disk is full or file permissions are incorrect. This exception is not handled in `bob_gaps_memory_turn`, which would lead to an unhandled exception and a 500 error response to the user instead of a graceful failure message in the chat. The test suite is missing a case for this scenario.
-   **Fix:** Wrap the file write operation in a `try...except` block and provide a user-facing error.
    ```python
    # In webchat/app.py, inside Chat.bob_gaps_memory_turn
    ...
    conversation.pop("pending_memory", None)
    conversation.pop("pending_memory_id", None)
    try:
        saved = append_profile_memory(self.root, pending_memory)
        content = f"Saved to `bob-brain/memory/profile.md`:\n\n`{saved}`"
        card_state = "done"
        card_reason = "Memory saved"
        files_to_log = ["bob-brain/memory/profile.md"]
    except OSError as e:
        content = f"Error: Could not save memory to profile. ({e})"
        card_state = "refused"
        card_reason = "Save failed"
        files_to_log = []
        # Optional: re-instate pending memory to allow for a retry
        conversation["pending_memory"] = pending_memory
        conversation["pending_memory_id"] = expected

    conversation["messages"][-1].update(
        status="done",
        content=content,
        provider="state",
        action_card={"id": request_id, "state": card_state, "executable": False, "reason": card_reason},
    )
    self.save(conversation)
    self.conversations[identifier] = conversation
    if files_to_log: # Only record turn if save was successful
        self.record_turn(conversation_id=identifier, ask=text, provider="state", jobs=[], files=files_to_log,
                    commits=[], confirmations=[pending_memory[:200]], refusals=[], open_items=[], request_id=request_id)
        state_ledger.record_webchat_turn(ledger, ask=text, provider="state", request_id=request_id)
    return self.public(conversation)
    ...
    ```

#### 3. (Low/Informational) Security: Screenshot ID Entropy

-   **File:** `webchat/bob_gaps.py`
-   **Line:** `114`, `192`
-   **Description:** The screenshot `capture_id` is generated using `secrets.token_hex(8)`, which provides 64 bits of entropy. While sufficient for preventing collisions and casual guessing, cryptographic best practices (e.g., OWASP) recommend at least 128 bits for unpredictable resource identifiers. Given the potential sensitivity of screenshots, increasing entropy is a low-cost improvement.
-   **Fix:** Increase the token size and update the validation regex.
    ```python
    # webchat/bob_gaps.py:114
    capture_id = secrets.token_hex(16)

    # webchat/bob_gaps.py:192
    def resolve_capture_path(root: Path, capture_id: str) -> Path | None:
        if not re.fullmatch(r"[0-9a-f]{32}", capture_id or ""):
            return None
        # ...
    ```

---

### VERDICT: FAIL

The implementation is strong, with excellent test coverage and attention to major security vectors like command injection. However, the failure to address resource exhaustion from generated files constitutes a significant operational flaw that is too severe for a `PASS` in a strict review. This issue could disable the application or the entire host machine over time. The branch should be updated to address the file growth issue before it can be approved.
This is a strict code review for branch `draft/webbob-voice-0927`. The changes introduce a real-time voice chat feature using Gemini Live, with a focus on product parity, security, and robustness, especially on mobile Safari.

The submitted code shows high quality, with excellent attention to modern web APIs (AudioWorklet, Web Audio), security (CSP, Permissions-Policy, CSRF), and concurrency (pinning reply IDs, snapshotting conversation state). The client-side JavaScript is well-structured and robustly handles various browser and network states. The Python changes correctly fix several potential race conditions in the core chat logic.

However, the review is critically hampered by the omission of several new, core files from the provided diff. The server-side logic in `webchat/voice.py` and the corresponding tests are absent, making a full security and functionality assessment impossible.

### BUGS / SECURITY / MISSING TESTS

#### 1. CRITICAL: Incomplete Diff Missing Core Files
**Severity:** CRITICAL (Process)
**Files:** `webchat/voice.py`, `webchat/test_voice.py` (and/or related tests), `webchat/test_voice_js.cjs`
**Issue:** The provided diff is incomplete. The new server-side voice logic, which is imported and used in `webchat/app.py` as `VoiceCalls`, is not included. This file (`webchat/voice.py`) is responsible for security-critical operations, including:
-   **Ephemeral Token Generation:** The method for creating and constraining Gemini Live tokens is not visible.
-   **Rate Limiting:** A rate limit mentioned in `VOICE-FIXED-0927.md` (`VoiceCalls._check_start_rate`) cannot be verified.
-   **State Management:** Logic for tracking call leases, ownership, and transcript versioning is not reviewable.
-   **Input Validation:** Server-side validation for all `/api/voice/*` endpoints is unknown.

Similarly, the new Python and JavaScript test files mentioned or implied by the review documents are missing, preventing verification of test coverage and correctness.

A strict review cannot be completed on a partial submission, especially when the missing parts are central to the new feature and have significant security implications.

**Fix:** The complete diff for the branch must be provided for review. This must include all new files, particularly `webchat/voice.py`, `webchat/voice_proof_server.py`, `webchat/voice_browser_proof.cjs`, and any new test files.

---
#### 2. BUG: Potential `KeyError` in Voice Tool Dispatch
**Severity:** BUG (Low)
**File:Line:** `webchat/app.py:~343`
**Issue:** When a voice-initiated tool is dispatched, the code looks up the original user message (`source`) and then accesses its properties to link the new assistant reply. The line `new_messages[0].update(voice_call_id=source["voice_call_id"], voice_turn_id=source["voice_turn_id"], ...)` uses direct dictionary access (`[]`). While the query to find `source` checks for `voice_call_id`, it does not check for the presence of `voice_turn_id`. If this key were missing for any reason, it would raise a `KeyError` and fail the request. Defensive coding would use the `.get()` method.
**Fix:** Use the `.get()` method for all properties accessed from the `source` message dictionary to prevent potential `KeyError` exceptions.

```diff
--- a/webchat/app.py
+++ b/webchat/app.py
@@ -341,8 +341,10 @@
                 source.update({k: v for k, v in new_messages[0].items() if k != "id"})
                 new_messages = new_messages[1:]
                 if new_messages:
-                    new_messages[0].update(voice_call_id=source["voice_call_id"],
-                        voice_turn_id=source["voice_turn_id"], voice_order=source.get("voice_order", 0) + 1)
+                    new_messages[0].update(
+                        voice_call_id=source.get("voice_call_id"),
+                        voice_turn_id=source.get("voice_turn_id"),
+                        voice_order=source.get("voice_order", 0) + 1)
             conversation["messages"] += new_messages
             if conversation["title"] == "New conversation":
                 conversation["title"] = text[:65]

```

---
### VERDICT: FAIL

While the visible code is of high quality and implements several impressive improvements, the verdict must be **FAIL**. A "strict code review" cannot pass when critical, security-sensitive components of the implementation are missing from the provided materials. The absence of `webchat/voice.py` and the associated tests creates a blind spot that is too large to ignore. The submission must be considered incomplete until all new files are provided for review.
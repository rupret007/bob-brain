The texting lane has made significant progress and addresses the previously cited false positives. The `texting.py` module correctly uses `hmac.compare_digest` for actor, token, and fingerprint validation. The browser proof in `webchat/browser_texting.cjs` explicitly confirms the "Not sent" path, aligning with the scope. The unit tests in `webchat/test_texting.py` cover success messages, `compare_digest` spying, error scrubbing, and persist-before-handoff logic.

Here are the findings based on the provided diff and scope:

**Focus Checklist Review:**

1.  **Chat.public() excludes codex_thread_id, retry_prompt, pending_job, pending_job_id, held_job before texting.public(); deep copy; no private leak:**
    *   `webchat/app.py` line 223-224: `filtered = {k: copy.deepcopy(v) for k, v in value.items() if k not in excluded}` and `return {k: v for k, v in self.texting.public(filtered).items() if k not in excluded}`. This ensures that the excluded keys are removed before passing to `texting.public()` and also from the final output of `public()`. The `deepcopy` ensures no mutable objects are shared.
    *   `webchat/test_texting.py` `test_core_exclusions_are_applied_before_texting_projection` explicitly verifies this behavior, including mutations in the `texting.public` patched function.
    *   **PASS**

2.  **hmac.compare_digest used for actor, yes-token, fingerprint:**
    *   `webchat/texting.py` line 200: `if (not actor or not hmac.compare_digest(actor, draft["actor"]) or ...`
    *   `webchat/texting.py` line 202: `not hmac.compare_digest(match[1], draft["token"]) or ...`
    *   `webchat/texting.py` line 203: `not hmac.compare_digest(fingerprint(draft), draft["fingerprint"]))`
    *   `webchat/test_texting.py` `test_token_comparison_timing_safe` explicitly patches and spies on `hmac.compare_digest` to confirm its usage.
    *   **PASS**

3.  **E2E browser proof + evidence agree on blocked "Not sent" path (mock success is separate unit test):**
    *   `webchat/browser_texting.cjs` line 100: `assert(result.messages.at(-1).content.startsWith("Not sent."));`
    *   `webchat/browser_texting.cjs` line 101: `await screenshot("phone-not-sent");`
    *   `webchat/browser_texting.cjs` line 103: `await page.locator('.text-draft-card[data-state="confirmed_not_sent"]').scrollIntoViewIfNeeded();`
    *   `webchat/browser_texting.cjs` line 109: `checks: ["login", "thread summary", "exact recipient and body", "edit clears consent", "new token after edit", "stale token rejected", "separate chat submission", "honest blocked receipt", "reload preserves consumed consent", "no horizontal phone overflow"]` explicitly lists "honest blocked receipt".
    *   `webchat/test_texting.py` `test_exact_confirmation_consumed_once_and_truthfully_blocked` covers the unit test for the blocked path.
    *   **PASS**

4.  **No real Andrea send without exact separate yes+token; consent consumed before handoff:**
    *   `webchat/texting.py` line 205: `draft.update(state="delivery_unconfirmed", token=None, approved_at=self.clock())`
    *   `webchat/texting.py` line 211: `persist(conversation)`
    *   `webchat/texting.py` line 212: `if self.andrea.deliver(draft["recipient"]["guid"], draft["body"]):`
    *   This sequence ensures that the consent is marked as consumed and persisted *before* attempting delivery via Andrea.
    *   `webchat/test_texting.py` `test_confirmation_persists_before_handoff_and_once_for_receipt` explicitly verifies the two `save` calls, one before and one after the `andrea.deliver` call.
    *   `webchat/test_texting.py` `test_disk_failure_does_not_claim_confirmation` and `test_receipt_save_failure_keeps_consent_consumed_after_restart` demonstrate robustness around persistence failures.
    *   **PASS**

5.  **Tests cover success message, compare_digest spy, error scrubbing, persist-before-handoff:**
    *   Success message: `test_separate_yes_success_message_content`
    *   `compare_digest` spy: `test_token_comparison_timing_safe`
    *   Error scrubbing: `test_transport_errors_are_safe_and_reads_never_follow_redirects`, `test_andrea_errors_do_not_leak_secrets`. These tests assert that sensitive information (passwords, tokens, internal paths) is not leaked in error messages or persisted state.
    *   Persist-before-handoff: `test_confirmation_persists_before_handoff_and_once_for_receipt`.
    *   **PASS**

6.  **Any REAL remaining security/test gap in texting scope:**
    *   The `TextingError` class is designed to prevent leaking sensitive information, and tests confirm this.
    *   The `local_url` validation is strict, preventing SSRF.
    *   The `_read` method in `BlueBubbles` has a strict allowlist for paths, preventing arbitrary API calls.
    *   The `redact` function is used on `answer["content"]` in `Texting.handle` and `Chat.reply_to_user` (via `enforce` and `repair_hollow_progress`), which is a good general security practice for output.
    *   The `redact` function is also used when preparing a draft's `target` (recipient details) to ensure no sensitive credentials are in the thread details before preparing a draft (`if redact(json.dumps(target, ensure_ascii=False)) != json.dumps(target, ensure_ascii=False):`). This is a strong control.
    *   The `test_payload_tampering_invalidates_binding` covers attempts to modify draft fields.
    *   The `test_thread_instructions_are_inert_and_private_from_providers` confirms that provider calls do not receive sensitive texting data.
    *   The `request_id` is used in `confirm` to prevent replay attacks from the same request.
    *   **PASS**

The code and tests demonstrate a robust implementation of the texting functionality within the defined scope and constraints.

VERDICT: PASS

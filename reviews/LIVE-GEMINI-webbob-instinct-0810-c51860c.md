# LIVE GEMINI Instinct review 0810

Tip: c51860cc36be4c44be722ba8175095b625666c4f
Model: gemini-2.5-pro
Prompt SHA256: a2aeec2b7fec86fe7550577fea412ae1332ad196c89167a8d167aff1b43dba74

REVIEWED_SHA: c51860cc36be4c44be722ba8175095b625666c4f

The implementation correctly adds read-only Instinct thread access, digest, and reply drafting capabilities to Web Bob, routing all actions through the existing `texting` framework.

- **Correctness:** The logic correctly uses the BlueBubbles read-only allowlist to fetch thread data. Command parsing in `instinct.py:handle` correctly distinguishes between status, digest, read, and draft requests. Recipient resolution in `instinct.py:resolve` is robust, prioritizing a pinned GUID and falling back to name matching with appropriate safety checks.
- **Ambiguous/Wrong Recipient Handling:** The `resolve` function correctly fails closed if multiple different recipients are named "Instinct," if the target is a group chat, or if multiple transports for the same recipient have ambiguous latest-message times. This prevents accidental message delivery to the wrong party.
- **Untrusted Relay Isolation:** Incoming message text from BlueBubbles is treated as untrusted data. The `private_excerpt` function quotes every line to neutralize hostile instructions. The `suggested_body` function uses local, conservative templates based on keyword categories, not raw message content, preventing prompt injection.
- **Privacy:** The `private_excerpt` function redacts phone numbers and emails from displayed message excerpts. The integration with `texting.py` ensures that all Instinct-related turns are flagged as `texting`, preventing sensitive thread content, draft bodies, and confirmation tokens from being sent to external providers, as confirmed by `Texting.provider_view`.
- **Confirmation Bypass/Replay:** The system correctly reuses the existing `texting` confirmation flow. Every send requires a separate, exact `yes <token>` message from the owner in the same authenticated session. The implementation is protected against replay attacks, cross-request forgery (the draft request cannot approve itself), and tampering, as validated by `texting.py:confirm` and `test_instinct.py`. Any intervening read or edit command correctly invalidates pending confirmations.
- **Regression Risks:** The Instinct logic is gated behind a specific keyword and is handled early in `texting.py:handle`. It does not alter the core logic for other texting commands or general job/provider routing. The `texting` module's own command parsing for non-Instinct messages remains unchanged. The change to `bob_parity_eval.py` correctly incorporates the new Instinct eval suite without altering existing tests.

No concrete blockers were identified. The code meets all stated requirements and demonstrates a strong security and privacy posture.

VERDICT: PASS

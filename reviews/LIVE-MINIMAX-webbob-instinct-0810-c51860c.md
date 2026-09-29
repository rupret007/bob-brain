# LIVE MINIMAX Instinct review 0810

Tip: c51860cc36be4c44be722ba8175095b625666c4f
Model: MiniMax-M2.7
Prompt SHA256: a2aeec2b7fec86fe7550577fea412ae1332ad196c89167a8d167aff1b43dba74

REVIEWED_SHA: c51860cc36be4c44be722ba8175095b625666c4f

## Review Findings

### Architecture Correctness
The Instinct module (`instinct.py`) correctly layers on top of the existing Texting infrastructure. Thread resolution requires either an exact display-name match ("Instinct") or a verified `BOB_INSTINCT_CHAT_GUID`, rejects multi-recipient threads, and uses newest-`lastMessage` only when participant addresses are identical. The read allowlist in `BlueBubbles._read` is restricted to two paths with password/port validation; no direct send capability exists.

### Ambiguous/Wrong Recipient Handling
The `resolve()` method fails closed when multiple threads share the name "Instinct" but have different recipient addresses, when timestamps are tied, or when the pin GUID is absent. The `handle()` method correctly routes "draft reply to Alex: I will check Instinct" to Alex, not Instinct, because the recipient target is validated against the composed match group (lines 103-104 in instinct.py).

### Untrusted Relay Isolation
- BlueBubbles uses SQLite config read via `mode=ro` URI before any HTTP call
- Cross-site/cross-origin requests are rejected in `app.py` dispatch
- Message excerpts pass through `private_excerpt()` to hide emails and phone numbers
- `Texting.provider_view()` strips all `texting`-flagged turns and draft cards from provider context
- The eval test `test_thread_content_drafts_and_tokens_never_enter_provider_context` confirms thread content, GUID, and tokens do not appear in provider calls or JSON serialization

### Privacy
The `texting` privacy flag on Instinct turns (set at line 117 in instinct.py `handle()`) ensures thread contents, draft bodies, and consent tokens are excluded from provider context. The `public()` method propagates this through `Texting.public()`. Audit records capture consent events without exposing token values to the model.

### Confirmation Bypass/Replay Prevention
- `confirm()` requires HMAC-digest actor match, conversation ID match, request ID mismatch (draft and confirm must be separate requests), and exact token match
- Epoch binding prevents cross-session replay after login change
- 300-second expiry enforced before delivery
- Fingerprint integrity check detects body/recipient tampering
- The test suite explicitly validates: different actor cannot approve, different chat cannot approve, same request_id cannot approve, expired token cannot approve, tampered draft cannot approve, and replay after successful delivery does not resend

### Regression Risks
- No new BlueBubbles write paths introduced
- Instinct integration is additive only; existing texting commands unchanged
- The `handle()` call in `texting.py` line 322-323 is inserted before generic texting command parsing, but returns `True` only for explicit Instinct patterns—no regression into other routing
- The eval's 118/118 bob_parity score confirms no regression in existing behaviors

### Test Coverage Gaps/Limitations
- Eval uses synthetic fixtures only; live BlueBubbles connectivity and Andrea bridge availability are unverified
- Attachment analysis is explicitly out of scope (digests warn "Attachments were not analyzed")
- Keyword flagging produces false positives/negatives; code correctly labels these as "keyword matches, not verified facts"

## Residual Limitations
1. Live thread identity and Andrea connectivity not validated offline
2. Keyword digest does not analyze attachments
3. `BOB_INSTINCT_CHAT_GUID` must be pre-configured for unnamed or disambiguated threads; no fallback to fuzzy match
4. Delivery uncertainty handled honestly but without retry or queue

VERDICT: PASS

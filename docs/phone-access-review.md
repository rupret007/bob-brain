# Secure phone access review — staged, not approved

Reviewed immutable candidate `1b077b4` via Git objects; no live runtime, network
configuration, phone session or macOS permissions were touched. Repository main
has no runtime. Production phone access remains NOT RUN, not a security PASS.

| Boundary | Source finding | Required acceptance evidence |
| --- | --- | --- |
| Backend exposure | `webchat/app.py:91` binds 127.0.0.1; constructor at 1757 rejects other bind addresses | Inspect the selected release listener and prove it is not publicly bound |
| Private HTTPS origin | `app.py:1764` accepts an exact HTTPS `.ts.net` origin | Verify the actual private-network ACL and phone identity; no public tunnel |
| Host/origin/CSRF | `app.py:1886` checks a single allowlisted Host; 1896 checks Origin; 1902 checks session CSRF | Requests with invalid Host/Origin/missing CSRF must fail on the selected build |
| Session cookie | `app.py:1880` includes HttpOnly, SameSite=Strict and Secure for HTTPS | Inspect phone response flags and prove revoked/expired sessions cannot read data |
| Logging | `app.py:1781` disables HTTP request-content logging | Inspect actual proxy/application logging policy without exposing cookies or keys |
| Approval cards | Existing consent semantics must survive a phone reconnect or tab reload | Recipient/body/time edits invalidate old approval; stale card cannot send |

Retain the private HTTPS access pattern already supported by the candidate. Do
not widen bind addresses, remove authentication or CSRF, expose a public tunnel,
or put shared passwords/tokens in phone URLs. Record proof against the full
release SHA using `evaluate_phone_access`; all eight checks need receipts. Its
tests validate fail-closed evaluation, not real phone security.

**needs Jeff: Screen Recording + Accessibility when desktop features are enabled.**
These are separate macOS permissions, not prerequisites for ordinary phone chat.
Jeff approves them in System Settings for the intended application. No code in
this branch opens or clicks prompts, changes TCC, grants permissions or controls
the desktop. Apple documents owner control of [screen recording](https://support.apple.com/guide/mac-help/control-access-screen-system-audio-recording-mchld6aa7d23/mac)
and [Accessibility access](https://support.apple.com/guide/mac-help/allow-accessibility-apps-to-access-your-mac-mh43185/mac).

Open evidence: all live listener/ACL, session revocation, phone and exact-build
adversarial request checks. The candidate source supports the proposed boundary,
but source inspection cannot establish current device grants or access control.

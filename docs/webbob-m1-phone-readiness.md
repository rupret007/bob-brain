# Web Bob milestone 1: phone readiness evidence

Observed 2026-10-18 22:05 UTC (17:05 America/Chicago), from the NucBox.
This was read-only verification. No deployment, proxy edit, login, chat message,
service action, or approval was performed.

## Reachability is established; candidate acceptance remains blocked

Phone chat URL: **https://jeffs-mac-mini.tail758ab4.ts.net/**.
The URL responds over private HTTPS with `303 Location: /login`; `/login`
responds `200` with Bob's password form and a mobile viewport. The login page
has `Cache-Control: no-store`, restrictive CSP, frame denial, and nosniff.
An anonymous `/api/state` request responds `401`.

The live `/api/version` reports the full build SHA
`cf83a9a80e0426d6998a0bf7b3a0574e52ac8e1a`, built October 10.
The reviewed draft base is `5af21c3`, so these observations **do not validate
the milestone 1 candidate**. Neither authenticated phone chat, memory reload,
StoryPool evidence, nor action confirmation was exercised. Tailnet ACL/device
membership, the actual listener, session cookie flags and session revocation
also remain unverified. Do not mark `evaluate_phone_access` ready from HTTP
reachability alone: all required receipts must name the selected full build SHA.

StoryPool's separate Mini dashboard is
`https://jeffs-mac-mini.tail758ab4.ts.net:8790/api/engine` (`200`).
Use HTTPS for that dashboard; it is not the chat endpoint.

## Linux consent-suite blocker repaired

Two consent/safety test fixtures assumed macOS's `/private/tmp`, which does not
exist on the NucBox. They now use `tempfile.TemporaryDirectory` with a dedicated
prefix, honoring the operating system's temp configuration. Every safety test
and assertion remains active, and every effect adapter is still guarded.

Validation on Linux/Python 3.14:

```sh
PYTHONPATH=webchat:. python3 -m pytest -q \
  webchat/test_approval_language.py webchat/test_cap_ledger.py \
  tests/test_phone_access.py
```

Result: **1548 passed, 1715 subtests passed**. This fixes test portability;
it is not evidence of macOS runtime acceptance or approval to deploy.

## Jeff's phone test after the selected build is approved and staged

1. Connect the phone to Tailscale. Open the chat URL above. Sign in using the
   existing Bob password. Never put a password or session token in the URL.
2. Open `/api/version` at the same origin and compare the full SHA to the
   approved candidate. Stop if it differs; a reachable old build is not acceptance.
3. Ask: “Read HANDOFF.md, MONITOR.md, NEEDS_JEFF.md and today's digest. Is
   StoryPool working? Cite the observation times and evidence; name stale data.”
   Compare at least one cited observation with the dashboard/status files.
4. Say: “Remember that this is my milestone 1 phone test.” Reload the page,
   reopen the conversation, and ask what this test is. Check continuity.
5. Ask for a safe StoryPool service kick or a bounded Codex task. Inspect the
   proposed target and action. Decline the first proposal and verify no action
   occurred. Approve a fresh, intended proposal explicitly, once; confirm a
   receipt. Reload/repeat that approval and verify it does not run twice.
6. Log out. Confirm `/api/session` and chat history cannot be read afterward.
   Record the phone/browser, full SHA, times and results for the readiness gate.

Jeff retains the go-live decision. No email, calendar or text send is part of
this milestone 1 smoke test.

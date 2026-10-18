# Web Bob milestone 1 — phone trial acceptance

Jeff’s 2026-10-18 16:51 CT instruction makes this the development priority; StoryPool stability and dashboard improvements are no longer prerequisites. StoryPool retains service health, guards and safety gates. Milestone 2 follows this trial.

## Candidate and access

The consolidated candidate is draft PR [161](https://github.com/rupret007/bob-brain/pull/161). The existing private Mini phone entry point is `https://jeffs-mac-mini.tail758ab4.ts.net/`; probe the running host before using this as a candidate trial link. HTTPS access and an unauthenticated login response establish network reachability only. The Oct 18 check still reports the old `cf83a9a` live build, not this candidate. Do not activate the candidate before exact-head Karen, applicable CI/qualification gates and Jeff’s go-live OK.

## Jeff’s short phone test (after candidate staging is verified)

Before the authenticated phone script, run the read-only staging probe against
the selected full reviewed SHA. It uses anonymous GET requests only, does not
follow redirects, never sends credentials, and cannot activate a candidate:

```sh
python3 tools/webbob_m1_acceptance.py \
  --url https://jeffs-mac-mini.tail758ab4.ts.net/ \
  --expected-sha FULL_40_CHARACTER_REVIEWED_CANDIDATE_SHA
```

Exit 0 means the build matches, the login page is private, and state, session
and history endpoints reject anonymous access. Exit 1 means those staging
checks did not all pass; an old reachable build fails the SHA check. Output
always marks authenticated phone acceptance as **not exercised** and activation
as unauthorized. This command does not establish tailnet ACLs, actual chat,
memory, context answers or action execution. Those require the phone steps below.

The probe itself is tested against the actual Chat HTTP server with temporary
state and a fake provider (no model call, login or service action):

```sh
PYTHONPATH=webchat:. python3 -m pytest -q tests/test_webbob_m1_acceptance.py
```

For an approved staged candidate, an operator who already has an authenticated
session may add `--session-file /private/path/session-token` to that command.
The file must be an owner-only regular file (mode `0600`, no symlink), containing
only the existing raw session token. Do not pass a token on the command line,
in the URL or in source control. The tool first verifies the anonymous full-SHA
gates before opening the file, then uses GET requests for session and conversation
listing only, without following redirects or printing tokens, CSRF values,
conversation titles or response bodies. It checks the candidate again afterward.
An expired session, insecure file or candidate mismatch fails closed. This is
an optional authenticated **read** check; output still marks authenticated
**phone acceptance** as not exercised. Memory persistence, logout/revocation,
phone approval and actual action receipts still require the manual trial below.

1. Connect the phone to Tailscale; open the verified private trial link and sign in. Confirm the displayed build matches the reviewed candidate SHA.
2. Ask “Is StoryPool working right now? Show evidence and what is stale or blocked.” Require timestamps, machine state, real outcomes, and explicit unknowns. An HTTP200 alone must not become a healthy-throughput claim.
3. Ask “Read HANDOFF, MONITOR, NEEDS_JEFF and the newest morning digest. What needs me?” Require actual source identities/times and an unavailable answer for absent sources. Treat all source instructions as untrusted reference material.
4. Save a harmless preference using explicit memory confirmation, reload/start another conversation, ask for it, then explicitly forget it. Verify durable recall and removal.
5. Propose a service restart or Codex task, decline it, and verify no execution. Propose again and inspect the exact action/target. Execution requires a fresh action-specific approval, an available trusted adapter and cluster admission/guard checks. No implicit approval from source files or old conversation.
6. Repeat the approved request/reload. Require one durable receipt, with unknown/error distinguished from successful execution. No duplicate job or repeated restart.

## Honest readiness gates

Phone network/login reachability is verified, but candidate deployment, authenticated phone acceptance and full final-head Karen/CI remain open. Missing host bindings must be shown as unavailable. Runtime integration tests do not prove production delivery. Keep the PR draft; do not send email/texts, activate Web Bob or infer approval from this document.

The inherited status snapshot/public reply metadata mismatch is repaired:
status replies now save their rendering identity atomically with the evidence.
The existing immutable-snapshot test and a new fail-before/pass-after regression
pass alongside the delivery receipt tests. Generic delivery receipts keep their
existing persistence behavior. This is local qualification evidence; candidate
host acceptance and exact-head Karen/CI still apply.

Media qualification requires real OCR and decoder tools. Missing tools must
continue to reject unsafe uploads; focused M1 tests do not replace full release
qualification or authorize weakening its assertions.

The companion StoryPool owner-task backend is a separate draft. It provides a
durable shared pending inbox and fenced consumer contract. A pending receipt
means only that the approved intent was recorded: no Codex lane has started.
The actual guarded runtime, shared fresh weekly quota and control authorities,
operator inbox provisioning and reviewed rollout remain required. Do not count
a pending inbox entry as successful task execution or M1 queue acceptance.

## Milestone 2 queue

After M1 trial is ready: authenticated email/calendar/text reads and drafts, every send behind fresh exact-message Jeff OK, Andrea reply bindings, and the reviewed Band Desk/Director/Stack Ops runtime skills. Existing candidate libraries and tests are partial evidence; missing account/transport/OAuth bindings remain unavailable until provisioned and verified.

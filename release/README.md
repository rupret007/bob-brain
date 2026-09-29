# Solo Web Bob releases

Jeff's 2026-09-29 instruction replaces the old Gemini/MiniMax BOTH_PASS and
worker-preflight release gates. Use `release/solo.py`; the old scripts and failed
receipts are historical evidence, not the active deployment path. Do not run the
council, vendor probes, or worker replay scripts during this solo effort.

Order: texting, gaps, media, voice, UI, read-only Instinct, remaining parity.
Only `draft/webbob-clean-0927` is the merge target. Never touch main or force-push.

Beyond-parity loops use `--feature improve`, preserving all cumulative bridge,
media, voice, memory and read-only Instinct checks. Each full check creates an
immutable numbered attempt directory. The latest two attempts at the exact SHA
must both pass full tests/evals/browsers/staging before activation; a failed or
interrupted run breaks the streak. Review the latest attempt's checks.json.
Every deploy also preserves its predecessor receipt so a failed attempt can be
followed by a fresh release without rewriting historical failure evidence.

Improvement checks also require the private Jobs result browser proof in Chromium
and WebKit: stale-response exclusion, close/Escape cancellation, the actual
15-second read bound and manual GET-only retry. This adds a gate; it does not
replace real voice or count independent offline supplements as release greens.

Startup recovery is also mandatory in Chromium and WebKit: initial session,
conversation-list and history failures, bounded read timeout, unauthenticated
redirect, automatic read-only recovery and continued polling with no mutations.

`check --root ROOT --feature FEATURE` runs full webchat, services, historical
release-guard and new solo-guard suites, parity evals, JS checks, the texting
browser proof and authenticated staging replay. Evidence is bound to a clean
candidate SHA and hash-checked. Review the source and record a separate self-review
with `reviewer: "Codex solo"`, exact `sha`/`feature`, `verdict: "PASS"`, concrete
`findings`, `checks_sha256`, and no `unresolved_blockers`.

Media and later releases also require Chromium/WebKit attachment proofs. Voice
and later releases require the voice JS/worklet suite and real Gemini audio in
both browsers on an isolated server, then real local Chromium/public WebKit
audio in each production round. Speech is synthesized locally; shared memory,
barge-in, a harmless version tool, persisted transcripts and resource cleanup
must pass. These product calls never invoke model reviewers or coding workers.
Synthetic microphone testing does not claim physical iPhone microphone proof.

Improvement voice checks also complete a requested longer story through the real
Gemini writing API and spoken playback, while retaining a brief-answer check.
The isolated server uses private fixture history and permits only the Gemini API
for writing, with no CLI fallback. Version checks require a new tool invocation
and spoken response after earlier writing tools; old tool activity cannot pass.

After a normal draft PR/clean-branch merge with the same tree, `deploy --root ROOT
--feature FEATURE --previous FULL_SHA --pr URL --checks PATH --review PATH`
checks the predecessor, saves fresh rollback snapshots, freezes the candidate,
and restarts only `svc-webchat`. It does not restart the job runner or other
services. Every production round checks both authenticated local and public
endpoints. Two consecutive rounds must pass. Any post-activation failure restores
and authenticates the immediate predecessor before publishing failure evidence.
`rollback --root ROOT --feature FEATURE --record RELEASE_JSON` provides recovery.

The current controller holds `conductor/locks/webbob-release.lock` through
preflight, snapshots, activation, both live rounds, recovery and publication.
A competing deployment or rollback fails before changing pins or evidence.
Nested recovery keeps the same ownership; exec children do not inherit it.
The private regular lock inode is permanent: never delete it to clear a busy
release. Kernel cleanup releases ownership when the controller exits.

Recovery accepts only that transaction's candidate, saved original pins or
predecessor snapshots, with matching build identities. Mixed pins from partial
activation are recoverable. An old rollback refuses to replace another release,
including a different deployment of the same SHA. Legacy receipts without
original pins can still recover their own candidate or predecessor snapshots;
an unfamiliar source requires investigation instead of guessing ownership.

Before changing pins, the controller now durably records its recovery identity,
snapshot hashes and publication paths in the private bounded
`conductor/locks/webbob-activation.json`. A killed controller leaves that journal
in place. Cooperating deploys refuse before preflight or snapshots until recovery
finishes; they never treat an interrupted round as a green. Run
`recover-pending --root ROOT --feature FEATURE` using the verified candidate's
`release/solo.py` to restore the recorded immediate predecessor. This command
does not activate the candidate or rerun its live rounds. The matching manual
`rollback` command also completes the journal and updates its saved live receipt.

Recovery verifies receipt identity, both current pins and both snapshot hashes
before any restart. It accepts mixed pins after a partial activation/rollback.
A missing progress receipt can be rebuilt from the journal, while changed or
unsafe receipts and unrelated pins are refused. Both authenticated predecessor
versions and recovery publications must succeed before the journal is removed.
Failure or process death during recovery retains the obligation for another
explicit attempt. Even a killed controller that published two live greens is
rolled back if it did not durably finish the transaction. Never delete a pending
journal to bypass recovery. Legacy rollback records must contain their original
snapshot hashes; missing provenance requires investigation.

This covers cooperating release controllers. Historical frozen scripts,
supervisor restarts and runtime work do not participate. Recovery is explicit,
not a supervisor/startup hook, and does not drain calls or replies. Shared work
admission, supervisor recovery and a compatible first-release procedure remain
necessary for atomic deployment drain. Neither current production nor this
candidate declares that compatibility.

The repository's `webchat/run.sh` now selects the Web Bob code pin before the
dispatch fallback, matching the existing installed launcher. Private subprocess
tests cover both pins, each fallback, drill selection and unchanged runtime data.
This aligns source selection only: it does not recover a pending journal or
make a partially switched pair of pins safe. Keep using the release transaction;
startup recovery and admission during interrupted activation remain unfinished.

The periodic `webchat/start.py` launcher leaves an existing `svc-webchat` session
alone when a health probe fails, including detached, attached or dead screen
entries. Unknown or failed screen inventories also refuse startup. Only a known
inventory without that session permits a new launch, with drills off by default.
This prevents an automatic health check from quitting a slow chat. It does not
share the release controller lock or recover an activation journal; the broader
startup/release coordination remains unfinished.

Always maintain at least 5 GiB free; recovery reserves and bounded atomic
evidence writes are retained from the existing release tooling. Authentication
secrets never appear in arguments, evidence or source control.

Live replay is strictly no-send, no-worker. Synthetic messaging, dispatch tests,
and historical fixture evals are labeled as such. They do not prove real delivery
or execution by stopped worker services. Real delivery is permitted only for the
final Jeff notification through Andrea after all readiness criteria are met.

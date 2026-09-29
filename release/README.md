# Solo Web Bob releases

Jeff's 2026-09-29 instruction replaces the old Gemini/MiniMax BOTH_PASS and
worker-preflight release gates. Use `release/solo.py`; the old scripts and failed
receipts are historical evidence, not the active deployment path. Do not run the
council, vendor probes, or worker replay scripts during this solo effort.

Order: texting, gaps, media, voice, UI, read-only Instinct, remaining parity.
Only `draft/webbob-clean-0927` is the merge target. Never touch main or force-push.

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

After a normal draft PR/clean-branch merge with the same tree, `deploy --root ROOT
--feature FEATURE --previous FULL_SHA --pr URL --checks PATH --review PATH`
checks the predecessor, saves fresh rollback snapshots, freezes the candidate,
and restarts only `svc-webchat`. It does not restart the job runner or other
services. Every production round checks both authenticated local and public
endpoints. Two consecutive rounds must pass. Any post-activation failure restores
and authenticates the immediate predecessor before publishing failure evidence.
`rollback --root ROOT --feature FEATURE --record RELEASE_JSON` provides recovery.

Always maintain at least 5 GiB free; recovery reserves and bounded atomic
evidence writes are retained from the existing release tooling. Authentication
secrets never appear in arguments, evidence or source control.

Live replay is strictly no-send, no-worker. Synthetic messaging, dispatch tests,
and historical fixture evals are labeled as such. They do not prove real delivery
or execution by stopped worker services. Real delivery is permitted only for the
final Jeff notification through Andrea after all readiness criteria are met.

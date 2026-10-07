# Solo Web Bob releases

Typed conversational answer turns, including short contextual follow-ups, use Gemini 3.8 Flash
with high thinking through the existing metered generateContent path. Ordinary,
operational, voice and image turns retain their checked Gemini 2.5 profile; this adds no tools.
The API uses native completed final text instead of asking the model to write
XML transport tags. Short native answers are valid; empty, thought-only and
truncated responses still fail. Legacy worker extraction is unchanged.
Gemini 3.8 reservations use the published post-promotion $1.50/$7.50 rates per
million input/output tokens; settlement uses $0.75/$3.75 through 2026 and the
higher rates from 2027. Output includes thinking. Pricing checked 2026-10-01 at
https://ai.google.dev/gemini-api/docs/pricing; cached input is conservatively
counted at the full input rate. A model upgrade is not evidence of answer quality:
the frozen candidate still needs the affected real sample and all release gates.

Jeff authorized Gemini on 2026-10-01 until its prepaid allowance needs refill.
The checked default local Gemini dollar ceiling is now absent; cost reservations
and settlements remain metered, and a finite runtime override can still tighten
admission (zero stops it). MiniMax remains $48 with95% admission. Recorded
spend is not an observed prepaid account balance. An explicit payment-required
or depleted-prepayment response stops text/worker attempts durably, including
new voice credential requests after that observation. Ordinary429rate limits
remain distinct. Existing voice calls and browser-only voice errors do not
write this funding marker. A failure to persist the marker stops the current
attempt and requires operator repair; durable future suppression is unverified
if the filesystem cannot save it. After Jeff confirms the funding problem is
resolved, the operator may use the checked `budget.authorize_refill_retry(note)`;
no background probe clears it or claims a verified balance. No purchase or
auto-reload is authorized by this policy.

The native receiver return procedure is `state/GROK-RECEIVER.md`. Install its
reference in Bob's existing local startup handoff, preserving older instructions.
Only native Grok may consume/checkpoint/ACK its batch. A compatibility-reader
bootstrap receipt does not prove current live publication or automatic return.
The private `receiver-evidence.json` binding described in `state/COORDINATION.md`
lets replies recognize independently checked historical native evidence while
keeping new batches unconsumed and current availability unknown.

Remaining-feature browser checks include clipboard fidelity, dictation draft
preservation/error recovery, and read-aloud lifecycle in Chromium and WebKit.
Clipboard/speech APIs are synthetic; physical audio is not claimed. Fenced code
keeps literal text and line breaks, while whole-message copy uses the original
message rather than rendered control labels.

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

Failed voice checks retain bounded protocol metadata: event order, successful
tool sends, completion counts, sanitized close classification and pending audio
and tool state. Only the proof-created conversation's result statuses and content
hashes are saved; the isolated server preserves the same metadata before deleting
its temporary fixture. No raw close reasons, tokens, model payloads or unrelated
conversation text enter these diagnostics. A diagnostic result is not a release
green, and an unexplained disconnect remains a recorded failure.

Hang up keeps its existing label node during streaming status updates: WebKit
can otherwise suppress a click whose text node changes between press/release.
The offline voice-availability gate exercises that race with trusted mouse input
on phone, resized phone and desktop layouts, plus touch/keyboard controls in both
browsers. Resources must close once while transcript saving is still blocked.
Real voice proof records bounded trusted activation/stop metadata before failure
cleanup; it still requires one actual click, resource closure and a saved transcript.

Improvement voice checks also complete a requested longer story through the real
Gemini writing API and spoken playback, while retaining a brief-answer check.
The isolated server uses private fixture history and permits only the Gemini API
for writing, with no CLI fallback. Version checks require a new tool invocation
and spoken response after earlier writing tools; old tool activity cannot pass.
Production Auto voice answers prefer healthy, admitted Gemini within the existing
compatible API route to reduce the wait before speech. Explicit provider choice,
capability routing, budget admission and fallback still apply. Deterministic
voice/route controls cover this preference and later typed turns; the isolated
Gemini-only audio proof does not itself verify production Auto selection.

After a normal draft PR/clean-branch merge with the same tree, `deploy --root ROOT
--feature FEATURE --previous FULL_SHA --pr URL --checks PATH --review PATH`
checks the predecessor, saves fresh rollback snapshots, freezes the candidate,
and restarts `svc-webchat`. An already enabled job runner is drained and
refreshed under supervisor/dispatch coordination; its process source and build
identity must match the dispatch candidate. An absent runner is not enabled.
Other services retain their identities. Every production round checks both authenticated local and public
endpoints. Two consecutive rounds must pass. Any post-activation failure restores
and authenticates the immediate predecessor before publishing failure evidence.
`rollback --root ROOT --feature FEATURE --record RELEASE_JSON` provides recovery.

When the owner has archived `SOLO-WORKER`, releases preserve the enabled worker
and reviewer services. They never recreate that marker. Live action checks use
an explicit conversation hold in fresh replay sessions and verify the truthful
hold receipt without queueing work. The isolated suite verifies actual dispatch.
An unscoped resource-use request must ask a specific question about the missing
objective and desired result, without inventing work or claiming generic readiness.
When a user-provided answer task is active, resources and deictic improvement
follow-ups remain answer turns. Progress questions inspect the active goal's
saved evidence without advancing it or reviving a suspended goal.
A Web Bob self-improvement goal must complete a source-backed
local routing investigation, with saved source hashes and actual probe outcomes.
Both live rounds independently verify that evidence and the transcript/marker
receipt. Subsequent exact resource/enable prompts use an explicit conversation
hold and must preserve evidence without queue writes. A separate fresh chat
checks unheld standalone enable/configuration behavior. The user's one bounded
unheld executor proof belongs in a dedicated conversation after LIVE_PASS; it
must verify actual execution and result/source integrity, not just acceptance.
Ordinary status questions still use server observations. Passing routing probes
or a local suite does not establish model-answer quality or Grok superiority.

The paired Andrea delivery protocol distinguishes provider submission, explicit
transport send, delivery, failure and unsupported/unknown status. Older sent
receipts prove submission only. Check delivery refreshes the immutable message
and approved scope through the authenticated status route; it cannot resend.
Failure evidence persists across weaker observations and requires a newer
positive delivery timestamp to establish recovery. The original confirmation
audit remains intact while later checks append observations. Live receipt replay
must prove a new successful inspection, not merely match a cached failure.
The synthetic browser and compiled cross-language proofs verify these outcomes
with no real texts. Actual phone delivery remains a separate owner check after
a fresh exact draft approval; a reply or same-account echo alone does not pass.

Once that suite has a verified result, improvement continuations retain its
receipt and source identity, link the full result, and prepare a saved local
capability worksheet. They must not repeat a test-log dump as if it answered a
new research goal. An explicit, unquoted Grok research instruction may advance
one bounded existing web-search attempt for that saved outcome. Inspection-only
and offline restrictions persist across turns and restarts. Search admission is
saved before network I/O; interrupted outcomes remain unknown and are not
automatically repeated. Search leads are not verified first-party evidence or
proof of Grok parity. Enable follow-ups report what is already configured;
they do not change settings or launch another worker.

Explanations may discuss supplied generic job states and negative evidence
without being replaced by an operational disclaimer. Such data can carry into
one adjacent explicit evidence follow-up, never from assistant claims or across
a corrected state. Direct, owned, named, current-effect and receipt-ID claims
still require real execution evidence, including when appended to a denial.

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
After a completed deployment has cleared that journal, a manual rollback binds
the feature's existing latest summary only when its complete release identity
matches the canonical receipt. Both publications must succeed before recovery
is complete; an unrelated release summary is left intact.
An unsafe or malformed optional summary cannot block recovery from the verified
canonical receipt: it remains untouched and a publication warning is recorded.

Runner startup launches one screen and gives bootstrap a 30-second monotonic
readiness window before declaring failure. Inventory probes use the remaining
deadline; a screen without its lifetime lock is not ready. The controller still
verifies the actual runner PID, locked script and exact dispatch source before
accepting activation. A runner that exceeds this window leaves a failed release
and a recovery obligation, never a second launch or permission to kill an
unidentified process. Explicit recovery can resume after identity is verifiable.

After stopping an enabled runner under release coordination, restart waits up
to 30 seconds for the known finite project tick and conductor pass to leave
the screen inventory before taking its restart baseline. It never kills those
tasks or claims that disappearance proves successful work. Every other service
identity remains strict during the wait and restart; failures retain exact
before/after inventories. If the wait fails before any pins or web process
change, the required stopped runner is restored from the unchanged dispatch
pin before the original failure propagates. Failed restoration retains both
errors and the recovery obligation. A disabled runner is never enabled here.
The final inventory is checked again after runner startup while coordination
is still held, so a persistent service lost during bootstrap cannot pass.

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

The journal records the obligation to preserve an enabled runner. A runner
observed after journal creation has a separate durable preservation receipt.
Drain recovers inactive claims but never kills live work to deploy. New code
fences runner admission while activation is pending; bound chat enqueue checks
the journal again under the queue lock. Recovery drains and cancels pending
candidate/held tasks before returning them to older execution rules, including
when pins already match the predecessor and no restart is needed. Original
requests and failed outcomes remain saved for explicit retry.

These guarantees cover the new runtime and cooperating release controllers.
The first predecessor's runner/watchdog do not honor the new pending journal.
Normal rollback holds supervisor/dispatch coordination through publication and
journal completion. A hard kill after starting that legacy predecessor releases
those process locks; historical code can then admit newly queued work before
explicit recovery. This is a migration limitation, not universal crash-safe
admission fencing. Frozen historical bytes are never patched. Recovery remains
explicit; it is not a supervisor/startup hook or a drain of model chat replies.

Always maintain at least 5 GiB free; recovery reserves and bounded atomic
evidence writes are retained from the existing release tooling. Authentication
secrets never appear in arguments, evidence or source control.

Live replay is strictly no-send and starts no workers. Synthetic messaging, dispatch tests,
and historical fixture evals are labeled as such. They do not prove real delivery
or execution by stopped worker services. The primary-assistant goal prohibits
texts, emails, posts, and an Andrea notification; report completion in chat.

The overnight conductor gate also forbids creating real pending text drafts,
recent-thread discovery, firing reminders, desktop capture, or appending a
private memory merely for a test. Those controls remain in isolated staging.
Live replay reads exact-build Andrea health, the protected explicit Instinct
thread (no discovery fallback), one configured Band Desk digest, reminder
listing and unchanged private-memory inspection. Instinct's direct service read
does not certify its product digest in production. The pinned retained owner
phone manifest and child hashes are checked without modifying the original
conversation; that is historical delivery evidence, not a new delivery test.

Retained song/audio HTTP storage and confirmation paths have isolated tests;
they do not prove new song generation or restore removed Songs controls.

An explicit request to return an unchanged upload on the current user turn can
now attach that owned file even if the model omits its attachment marker. The
selector requires a unique target or explicit set, rechecks conversation
ownership at completion, and uses the existing cancellation and retry handling.
Ambiguous targets, edited or converted deliverables, conditions, quoted
instructions and unclassified companion clauses do not trigger automatic
returns; they retain the existing model-marker path. This does not add file
editing, external sending or selection from previous turns. The failed live
media check retained the delivered answer but not raw provider output, so the
original cause of the missing marker remains uncertain. Release gates remain
unchanged; regression coverage now includes a substantive marker-free answer.

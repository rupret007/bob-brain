# Candidate runtime integrations

These paths are part of the draft candidate. They do not install, activate or
authorize Web Bob, messages, calendar writes or work lanes.

## Outbound draft safety

Text drafts continue to use the existing exact-token Andrea bridge. A separate
`no`, `don't send`, `do not send`, or `cancel text` cancels an unconsumed text
draft and clears its token. A declined token cannot send after replay or restart.
If a text was already handed off, refusal preserves its actual delivery state
and reports that outcome; it cannot undo a submission or claim nothing was sent.

Personal email/note/booking drafts now record a durable `declined` state for a
separate refusal. A later `yes`, `send it`, or `go ahead` does not reactivate that
draft. When several actions are pending, a bare refusal asks which draft; use
`cancel email draft`, `cancel note draft`, or `cancel booking draft` to identify
the personal action. Declining never releases a saved hold. A new draft replaces
the old personal draft and requires fresh review.

Email sending is unavailable in this candidate's Chat runtime. Its concrete
draft and approval guidance say so; they never save standing approval for later
delivery. Resolve the actual recipient/thread and configure/review the trusted
transport before requesting fresh exact-message approval. The imported
`MessageDraftGate` and `AndreaReplies` libraries are not installed email or
mention ingress transports. The existing Andrea text bridge remains separate.
No new sender, OAuth grant, background retry or fallback is installed here.

Personal draft turns remain in Jeff's authenticated history. Their user/reply
pair, private draft state and title are omitted from generic provider context;
legacy draft rows are recognized before a new save. Shared coordination and
typed-reply observation journals do not publish their recipient/body. The shared
handoff retains only its existing private-action summary/pending count. This
does not remove any previously appended historical journal entry.

Ten new real Chat/authenticated HTTP tests exercise refusal, restart/request
replay, competing drafts, holds, fresh drafts, legacy privacy, missing transport,
conditional/draft-only cues, authentication and CSRF. All use isolated state;
real sends, provider services and work dispatch are forbidden in those tests.

## Morning calendar

In an isolated authenticated staging conversation, submit:

```text
every morning at 8am do show my calendar today
```

Web Bob presents a draft. Confirm the exact `yes wbrem-…` in a separate Jeff
message to schedule it. Until then no routine is saved and no calendar request
runs. `draft only` or `provided I agree` cannot schedule anything. Cancel using
the receipt's `cancel routine ID`. Existing owner/actor checks, holds and
cancellation apply across restart.

The existing `webchat.Reminders` JSON store is authoritative for chat reminders
and routines. The imported SQLite `webbob.ReminderStore` and
`MorningCalendarRoutine` are not instantiated by the chat runtime. No migration
or second scheduler is installed. The live predecessor's state layout still
needs a Mini staging check before deployment.

The scheduler invokes a narrow callback to `CalendarActions.read('today')`.
The host's existing Google Calendar adapter reads the primary calendar using
America/Chicago day bounds. No attendee, send, create, model or work-dispatch
adapter is available in this routine. Missing/expired OAuth reports needs-auth;
it never means an empty calendar or a successful lookup. Host OAuth setup is
still required and must not be pasted into chat or committed.

The same reminder notice identity and durable local action receipt prevent
duplicate visible notices/reads on replay. One overdue occurrence catches up;
the next run returns to the Chicago morning, including DST. Read errors appear
once for that occurrence; no immediate retry loop or repair is triggered.
An ambiguous/crashed local action remains unconfirmed rather than being read
again with the same occurrence identity. Results stay private in chat without
OS alerts. Event titles are displayed as data and never processed as actions.

## Local file approval and worker timeouts

An exact separate `yes wblocal-…` consumes the durable approval in the parent
before it launches a file worker. The worker checks that conversation and
approval request, saves its execution claim, then performs the existing bounded
file operation. Receipt locking still has its existing deadline. Target-file
I/O stays in the killable interpreter; no threaded-server fork is introduced.

A worker startup failure, timeout or lost result leaves the action unconfirmed
unless a completed receipt was saved. Repeating an approval, including after
restart or from another tab, cannot relaunch it. Inspect the target before
making a new request. Cancelled/expired drafts, holds, private-path exclusions,
credential refusals and file-fingerprint checks retain their existing rules.
The deadline tests exercise startup timeout, stalled file I/O, storage/launch
failure and concurrent real workers using only temporary files.

## Explicit skills

Select a skill at the start of the current message: `$band-desk`, `Band Desk`,
`$stack-ops`, `Stack Ops`, `$director: BRIEF`, or `Director: BRIEF`.
Merely discussing a skill or quoting a tool result does not select it.
Each turn requires explicit selection; a prior selection grants no continuing
authority. Requests with a work-lane assignment are held in chat.
The existing `band desk status`, `band desk digest` and `band desk read`
commands retain their sourced watcher/private thread behavior. Use `$band-desk`
or `Band Desk` for the GitHub operations skill.

- Band Desk performs one bounded, noninteractive GitHub read using `gh api
  graphql --hostname github.com`, a fixed query for StoryBoard and RadDadSite,
  and at most 20 open PRs per repo plus 20 RadDadSite issues. It reports observed
  default-branch/head SHA and CI separately from unverified Karen status.
  Wildflower matches refer only to fetched RadDadSite PR/issue pages; booking,
  dates and publication remain unknown without evidence. No arbitrary repo,
  command, mutation or URL comes from chat or tool text.
- Stack Ops uses `webbob.storypool_status.collect_status` for fixed bounded
  local files/dashboard and escalation notes, plus the configured shared
  Mini/NucBox snapshot's availability/time/freshness. It preserves missing,
  stale and unknown labels; escalation notes are quoted untrusted excerpts.
  No restart, repair, dispatch, file write, merge or release tool is exposed.
  Real shared-source provisioning/Grok pickup remains a separate staging gate.
- Director loads this release's reviewed skill into the current provider
  instructions. The supplied brief/media remains user data. It drafts a
  treatment/shot plan without rendering, paid generation, publishing, sends,
  repository changes or work dispatch. Media limitations remain explicit.

All three load only fixed definitions from the shipped `skills/` tree.
Status responses are rendered by the host; fetched PR/issue/status text cannot
become model instructions or consent. Skills do not invoke sends and do not
release saved holds. The Director uses the existing model admission/usage
boundary; no Grok lane or default Claude lane is introduced.

## Saved reply delivery

Chat uses saved history as its reply transport. Completed public typed replies
now expose a stable display ID plus a SHA-256 binding of the actual saved text,
artifact and attachment metadata. The browser observes only currently visible
rows after rendering and posts bounded authenticated, CSRF-protected batches to
`/api/reply-receipts`. The existing `ChatReplyJournal` records those observations
idempotently, privately, and without storing reply text. Status-card refreshes
do not create new text versions. Changed text/artifacts get a distinct exact
version while retaining one display row.

History GETs remain read-only. Lost observation responses never submit a message,
call a model or invoke a sender; reload may repeat only the idempotent receipt.
Unacknowledged visibility stays unknown. A browser observation is not a human
read receipt, audio playback proof, action receipt or send approval. Private
texting/memory, voice, incomplete, foreign and stale rows cannot be acknowledged.
Automatic reminder notices keep their existing durable occurrence receipts and
are excluded from this typed-turn observation path.
Journal failure leaves the saved answer intact. Existing request IDs, duplicate
submission handling, pending-generation recovery and conversation persistence
remain authoritative; the push/retry `deliver` method is not used for polling.

Eight runtime/real authenticated HTTP cases cover restart, concurrent reloads,
lost receipt responses, exact changed bodies/long artifacts, foreign/private
rows, private permissions, unavailable stores and unchanged holds/model counts.
`test_reply_receipts.mjs` tests the actual UI observation code with deterministic
frames and network loss. Actual Chromium/WebKit Mini rendering/reload acceptance
is still required; the host browser binaries/dependencies are unavailable here.

Staged release packaging: [WEBBOB-GO-LIVE.md](WEBBOB-GO-LIVE.md).

## Offline validation

```bash
PYTHONPATH=webchat:state python3 -m unittest test_outbound_draft_safety test_personal_drafts test_texting_draft_routing -v
PYTHONPATH=webchat:state python3 -m unittest test_calendar_routine_runtime test_skill_runtime -v
PYTHONPATH=webchat:state python3 -m unittest test_reply_delivery_runtime test_reply_lifecycle -v
node webchat/test_reply_receipts.mjs
python3 -m unittest discover -s tests -p test_storypool_status.py -v
```

The runtime tests use real Chat/provider-prompt boundaries with fake calendar
and status transport data. They prohibit sends/work dispatch and make no model
calls. They cover approval, cancellation, restart, DST, unavailable auth,
untrusted event/source instructions, explicit selection, fixed GitHub reads,
failed/partial status, source time/freshness, and code imports outside the repo.
They do not establish Mini OAuth, full release qualification or go-live consent.

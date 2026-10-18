# Candidate runtime integrations

These paths are part of the draft candidate. They do not install, activate or
authorize Web Bob, messages, calendar writes or work lanes.

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

## Offline validation

```bash
PYTHONPATH=webchat:state python3 -m unittest test_calendar_routine_runtime test_skill_runtime -v
python3 -m unittest discover -s tests -p test_storypool_status.py -v
```

The runtime tests use real Chat/provider-prompt boundaries with fake calendar
and status transport data. They prohibit sends/work dispatch and make no model
calls. They cover approval, cancellation, restart, DST, unavailable auth,
untrusted event/source instructions, explicit selection, fixed GitHub reads,
failed/partial status, source time/freshness, and code imports outside the repo.
They do not establish Mini OAuth, full release qualification or go-live consent.

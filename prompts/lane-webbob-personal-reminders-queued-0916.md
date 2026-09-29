# lane-webbob-personal-reminders-queued-0916 (QUEUED — draft-only, independent of the texting deploy chain)

You are Cursor on Jeff's Mac Mini. Build personal todos/reminders for Web Bob from scratch — this does not exist on either Bob the Bot or Web Bob today. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No deploy.

## Why
`conductor/reviews/WEBBOB-PARITY-0927.md` rows 5 and 11 confirm: no calendar/reminder-app integration exists for desktop Bob or Web Bob. This is a genuine two-sided gap, not something to reverse-engineer from an existing feature. `WEBBOB-PARITY-0927.md` build item #6 sketches the shape: "Simple reminder store + piggyback on the existing job-runner tick cadence, surfaced in chat and the reports tab."

## Product requirements
1. Jeff can say something like "remind me to X at/on Y" in Web Bob chat; it's stored as a structured reminder (not a free-text memory line).
2. Reminders fire as a chat message (and/or reports-tab entry) to Jeff at the right time — piggyback on the existing job-runner tick, do not build a second scheduler.
3. Reminders **only** notify Jeff. They must never auto-trigger a job, text send, PR action, or any other side effect on their own — this is the hard safety rule from `WEBBOB-PARITY-0927.md` build item #6.
4. Jeff can list/cancel his own reminders from chat.

## Reuse
- Existing job-runner tick cadence (`services/job-runner.sh`, `web_dispatch.tick()`) for the fire mechanism.
- Existing "song projects" save/list API (`providers.py:36-38`) as a rough pattern for a small persisted-list feature, though reminders need time-based firing which that doesn't have.

## Deliverables
1. Reminder store (create/list/cancel) + tests.
2. Time-based fire mechanism riding the existing tick, with a test proving it never calls into job/text/PR code paths.
3. Chat command surface + reports-tab view.
4. Write `conductor/reviews/PERSONAL-REMINDERS-FIXED-<timestamp>.md` with tip SHA and test counts. Draft PR only, never merge/deploy.

## Stop
Stop when the fixed/ready marker exists. This is a new-feature build with no existing deploy-order dependency, but still do not deploy — draft-only until Jeff prioritizes it. Print tip SHA and marker path.

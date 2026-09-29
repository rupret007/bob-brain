# lane-webbob-teammates-status-queued-0916 (QUEUED — investigate + ask Jeff before building for "Band Desk")

You are Claude on Jeff's Mac Mini. Figure out what, if anything, Web Bob should surface about the teammates Karen and "Band Desk." Do NOT use Grok/xAI. No force-push. No Jeff notify/text (except the one clarifying question this lane is explicitly allowed to ask, per below). No deploy. Andrea is already covered by the texting lane — do not duplicate that work here.

## Why this lane exists
`conductor/reviews/WEBBOB-PARITY-MATRIX.md` rows 24-25: the parity-matrix task named three teammates (Karen / Andrea / Band Desk). Andrea = the existing texting relay (row 13, already tracked). Karen resolved to a real, evidenced person: `wt-webjam-polish/PRE_KAREN_QA.md` — a human WebJam QA reviewer whose independent review gates Bob's WebJam work, with no bot-to-Karen integration today. "Band Desk" has **zero occurrences** anywhere in this repo under that name — not in `BOB-HANDOFF.md`, not in any `conductor/` file, not in any workspace. This lane should not guess what it means.

## What to do
1. **Karen**: read `wt-webjam-polish/PRE_KAREN_QA.md` in full for the current shape of her review gate. Decide whether a read-only "Karen QA status" surface (e.g., "waiting on Karen's review of PR #X") belongs in Web Bob's reports tab, following the same read-only pattern as the who's-running-view lane. Do not build a way for Web Bob to contact Karen directly — she is a human reviewer outside Bob's messaging surface entirely (not Andrea/BlueBubbles).
2. **Band Desk**: do a thorough search (already done once here, found nothing) and, if still nothing turns up, write the specific question for Jeff rather than inventing a feature: "What is 'Band Desk' — is it a person, a tool, a physical location, or a mishearing of something else?" Do not write any code for this until Jeff answers.

## Deliverable
Write `conductor/reviews/TEAMMATES-STATUS-<timestamp>.md`:
- A concrete recommendation (with evidence) for whether/what to build for Karen, or a note that nothing is warranted yet.
- The exact open question for Jeff about "Band Desk," clearly separated from anything already answered.

## Stop
Stop after `TEAMMATES-STATUS-<timestamp>.md` exists. Do not start any coding screen for Band Desk. Print the file path and the one open question for Jeff.

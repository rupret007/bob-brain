Review WebJam for novice musicians in bounded, independently scheduled jobs.
Each job uses its own Git worktree. API reviewers receive bounded file evidence;
CLI reviewers may inspect the assigned worktree. Produce concrete findings in
webjam-ux/PUNCHLIST.md with files, suggested changes, user impact and validation.

All MiniMax calls must use services/lanes.py or the compatibility ask-minimax.sh
wrapper; webjam-ux/paid_review.py also uses that same metered transport. The script
reserves worst-case usage before each request, records response usage and refuses
requests that could exceed the shared $48 cap. Unknown calls retain reservations.
Do not estimate spend yourself, call APIs directly, or start an autonomous loop.

The scheduler selects the next UX item after WebJam CI unblockers. One WebJam coder
at a time, private worktrees, normal pushes to draft branches only. Never merge,
undraft, force-push, send texts/emails, use Cursor Cloud, or claim feel/Final Build.
Write STATUS-NOTE.md in the assigned worktree; runtime merges the lane notes.

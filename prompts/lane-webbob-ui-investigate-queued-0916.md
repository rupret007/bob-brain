# lane-webbob-ui-investigate-queued-0916 (QUEUED — investigate scope only, do not build or deploy)

You are Claude on Jeff's Mac Mini. Figure out what "UI" means as the 5th item in Web Bob's fixed deploy order (texting → gaps → media → voice → **UI** → Instinct). Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No deploy. Read-only investigation and a written report only — no code changes.

## Why this lane exists
`conductor/reviews/WEBBOB-PARITY-MATRIX.md` row 18 found no dedicated branch, tip SHA, or review file for "UI" anywhere in `conductor/reviews/` or `conductor/prompts/`. It only ever appears bundled as "Voice / UI: behind" in `LOOP-RUN-0810-SUMMARY.md` and `LOOP-RUN-0916-SUMMARY.md`, always paired with voice, never broken out on its own. Before anyone builds anything for "UI," we need to know what it's supposed to cover.

## What to check
1. Search all `conductor/reviews/*.md`, `conductor/prompts/*.md`, `conductor/handback/*.md`, and any `WEBCHAT-READY*.md` / `WEBCHAT-FAILOVER*.md` design docs for any UI-specific requirement that was scoped but never given its own branch (mobile responsiveness? jobs-browser polish? a specific screen width bug? something from `WEBBOB-PARITY-JOBS-0927.png`/`WEBBOB-PARITY-REHEARSAL-JOBS-0927.png` screenshots?).
2. Check whether "UI" was ever Jeff's own words (grep `HANDBACK-LOG.md` for "UI" near a Jeff ask) versus an assumption baked into the deploy-order line by an earlier autonomous tick.
3. Check current webchat UI test coverage (`browser_e2e.cjs`, `capture_iphone.cjs`, any `test_*_js.cjs`) for gaps that might be what "UI" was meant to close.

## Deliverable
Write `conductor/reviews/UI-SCOPE-<timestamp>.md`: either (a) a concrete definition of what "UI" covers with evidence, so a real build lane can be queued next, or (b) an honest "no evidence found, ask Jeff" conclusion with the specific question to ask him. Do not guess a scope and start building against it.

## Stop
Stop after `UI-SCOPE-<timestamp>.md` exists. Print its path and the one-line conclusion.

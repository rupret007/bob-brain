# WEBBOB-UI-READY-0927

Draft lane: polished phone-first Web Bob chat shell and Jobs page. **Do not merge from this note alone.**

## Summary

- Rebuilt the chat shell for a dark, phone-first layout: cleaner bubbles, typography, spacing, sticky glass composer with attach + dictate + waveform live-voice slot, and a subtle monospace build SHA in the header.
- Removed the Songs/music tab and quick chip from the shell; song APIs remain on the server but the UI no longer surfaces them.
- Refreshed the Jobs view with card layout showing status, age, project, task, and per-LLM pills; finished jobs use the same card language.
- Added static UI contract tests and an optional Playwright shell smoke test.

## Screenshots

| View | Before | After |
|------|--------|-------|
| Phone chat | `reviews/WEBBOB-UI-0927/before/phone-chat.png` | `reviews/WEBBOB-UI-0927/after/phone-chat.png` |
| Phone jobs | `reviews/WEBBOB-UI-0927/before/phone-jobs.png` | `reviews/WEBBOB-UI-0927/after/phone-jobs.png` |
| Desktop chat | `reviews/WEBBOB-UI-0927/before/desktop-chat.png` | `reviews/WEBBOB-UI-0927/after/desktop-chat.png` |
| Desktop jobs | `reviews/WEBBOB-UI-0927/before/desktop-jobs.png` | `reviews/WEBBOB-UI-0927/after/desktop-jobs.png` |

Capture helper (private listener, no deploy): `webchat/run_ui_review_capture.py reviews/WEBBOB-UI-0927/after`

## Changed files

- `webchat/static/index.html` — layout, composer, Jobs header, removed Songs
- `webchat/static/style.css` — dark theme, bubbles, composer dock, job cards
- `webchat/static/app.js` — Jobs card rendering, song-less shell guards, attach focus
- `webchat/capture_iphone.cjs` — tab list without Songs
- `webchat/capture_ui_review.cjs`, `webchat/run_ui_review_capture.py` — review screenshots
- `webchat/browser_ui_shell.cjs`, `webchat/test_ui_shell.py`, `webchat/test_ui_browser.py` — UI tests
- `webchat/.gitignore` — ignore `node_modules/`
- `reviews/WEBBOB-UI-0927/**` — before/after PNGs

## Verification

```bash
bash reviews/run-webbob-tests.sh
cd webchat && python3 -m pytest test_ui_shell.py test_ui_browser.py -q
node --check webchat/static/app.js
```

**Last run:** `reviews/run-webbob-tests.sh` — **pass** (254 webchat + 118 services + quiet_hours_js).

## Constraints honored

- No reply/backend logic changes beyond static Jobs rendering in `app.js`.
- No deploy, no service restart, no `.password` printed.
- Draft branch only; not merged.

## Remaining risks

- Attach button is a UX slot (focuses composer); file upload still flows through chat/API elsewhere.
- Playwright browser test skips if `webchat/node_modules/playwright` is not installed locally.
- Light-mode users now see the fixed dark shell (`color-scheme: dark`).

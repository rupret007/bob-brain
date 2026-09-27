# Web Bob media ready — 2026-09-27

**Worktree:** `workspaces/wt-webbob-media-0927`  
**Branch:** `draft/webbob-media-0927` (draft only; do not merge or undraft)  
**Rebased onto:** `dcc2c8e` (`Complete authorized project pushes and wait for terminal live results`)  
**Goal:** Web Bob photo/video/file in and out on phone-sized Safari layouts, matching or beating everyday Bob-the-Bot chat media behavior.

## Rebase and integration

- Rebased the media lane onto `dcc2c8e`, resolving conflicts in `webchat/app.py`, `providers.py`, `static/app.js`, `index.html`, and `style.css`.
- Kept **dcc2c8e** chat-intent, build identity in provider prompts, and **reply_authority** conversation context while preserving media upload, vision, outbound markers, and Safari composer flows from the media commits.
- Restored the **iPhone conversation sheet** (`#conversations-dialog`, `#new-chat-dialog`) and **Status quick chip** POST isolation so staged attachments are not consumed by quick actions (required by browser regressions).

No production `:8787` deploy, service restart, texts, or Grok/xAI usage. No secrets printed.

## E2E coverage (iPhone Safari sizes)

Automated with Playwright **WebKit** (iPhone 13 device profile) and **Chromium**, against a disposable localhost fixture (`webchat/media_browser_test.py` + `webchat/test_media_browser.cjs`):

| Check | Evidence |
| --- | --- |
| Photo upload, preview, send, assistant echo | WebKit + Chromium |
| Video upload, inline playback, seek | WebKit (MOV) + Chromium (WebM) |
| File upload and **download** (`notes.txt`, PDF) | Both engines |
| HEIC preview when `sips` available | Both engines |
| Quick **Status** chip does not attach staged media | POST body `attachments: []` |
| Conversation switch preserves composer drafts | Dialog sheet flow |
| Idempotent retry after failed send | Same `request_id` |
| 44px remove targets | Measured bounding box |
| CSP (no blob/FileReader bypass) | Init script guards |
| Viewports **390×844**, **390×500**, **844×390** | Composer visible in reduced height and landscape |

## Full verification (2026-09-27)

```text
bash reviews/run-webbob-tests.sh
```

| Suite | Result |
| --- | --- |
| `webchat` pytest | **282 passed** |
| `services` pytest | **120 passed** |
| `test_quiet_hours_js.mjs` | **PASS** |
| `node --check` app.js + test_media_browser.cjs | **PASS** |
| `python3 webchat/media_browser_test.py` | **WebKit + Chromium PASS** |
| `py_compile bootstrap.py` | **PASS** |
| `git diff --check` | **PASS** |

## Parity vs Bob-the-Bot

| Capability | Web Bob (this branch) | Notes |
| --- | --- | --- |
| Send photos from phone | Yes | Raw `File` upload, preview chips, Gemini vision path |
| Send videos | Yes | 35 MB cap, Range/HEAD serve, playsinline, download fallback |
| Send/download files | Yes | PDF/text/JSON/etc.; authenticated GET with `download=1` |
| Assistant returns media | Yes | Marker strip + resolved attachments in UI |
| iPhone composer UX | Yes | Sheet picker, draft isolation, 44px targets, multi-viewport e2e |
| Physical device sign-off | Not claimed | Playwright WebKit profile is automated evidence only |

## Related docs

- `reviews/MEDIA-FIXED-0927.md` — finding dispositions from the media fix pass  
- `reviews/WEBBOB-MEDIA-0927.md` — original feature summary  
- `reviews/CURSOR-REVIEW-MEDIA-0927.md`, `reviews/GEMINI-REVIEW-MEDIA-0927.md` — read-only review inputs (untracked in repo until added separately)

## Remaining risks

- Live model vision/spend not exercised in the browser fixture (stub provider only).
- HEIC preview depends on macOS `sips` in CI/dev; download of original HEIC still works when preview tooling is absent.
- Rebased branch history diverges from prior remote tips; push may require an explicit lease update on the draft remote (never force-push to shared/default branches).
- **2026-09-27 push:** `git push brain draft/webbob-media-0927` rejected (non-fast-forward after rebase). Local commit `0953d66` is ready; updating the draft remote needs a one-time `--force-with-lease` on this draft branch only, or a maintainer-chosen integration strategy.

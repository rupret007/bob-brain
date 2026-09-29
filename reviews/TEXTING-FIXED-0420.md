# Texting — FIXED — 0420

Recorded: 2026-09-28 04:33:12 CDT

**Combined tip:** `ce2482cce311ce4317c1b3aca316f1ca446aeddb`
**Branch:** `draft/webbob-texting-onto-a777736`
**Remote:** `brain/draft/webbob-texting-onto-a777736` — regular push completed; remote SHA verified with `git ls-remote`.
**Worktree:** `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420`

## Lineage

This is a two-parent merge commit:
1. Live integrate baseline: `a777736b3f0a37c82b0c4c62be8c91117c4c9881`.
2. Fetched texting tip: `97513468016488ebe42ca1919e507db99fc0a15f`.

Both parents are verified ancestors of the combined tip. The worktree was clean after commit and push.

## Conflict dispositions

- `webchat/app.py`: kept integrate's `status_reply`, `reply_authority`, `status_observation` binding and durable observations, `worker_assignment.requested_workers` / `issue_followup`, task/council dispatch, and provider metadata filtering. Added texting's `Texting` import and injectable instance, `texting.public` filtering, early `texting.handle`, and `persist_texting` clearing `pending_job`, `pending_job_id`, `pending_council`, and `pending_council_id` before saving. Preserved `actor` on `submit`, populated from the authenticated session digest, and `texting.provider_view` for model context. No integrate job routing was dropped.
- `reviews/WEBBOB-EVALS-0927.md`: retained the integrate rubric/gate history and isolated texting evidence together. Earlier 24/24 plus 3/3, 31-case, and 33-case notes are labeled historical. The current 96-case parity assertion remains in the passing webchat suite. No earlier score or BOTH_PASS is presented as a verdict on this new SHA.
- Texting source, tests, fixtures, browser/proof scripts, static cards, screenshots, and existing evidence were brought over. All 51 integrate-only paths match integrate byte-for-byte. All 27 texting-only paths match texting except trailing whitespace removed from two imported Markdown notes to satisfy the diff check. The six shared files were combined and reviewed.

## Offline validation of the combined source tree

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | Exit 0: 381 run, 380 passed, 1 optional browser skip; 43.438s |
| `python3 -m unittest discover -s services -p 'test_*.py'` | Exit 0: 131 passed; 3.712s |
| `node --check webchat/static/app.js` | Exit 0 |
| `git diff --check` | Exit 0 |
| `git diff --cached --check` before commit | Exit 0 |
| `git diff HEAD^1 HEAD --check` after commit | Exit 0 |

The single skip is `TextingE2ETest.test_browser_proof_when_playwright_available`, because Playwright is unavailable to Node in this checkout. Texting unit and HTTP E2E checks passed against synthetic loopback fixtures. Screenshots retained from the texting tip are historical; no new browser proof or real delivery is claimed.

`BOB_ROOT` and `BOB_WEBCHAT_DIR` were pointed at an isolated data tree. Services passed with `TMPDIR=/private/tmp`. Two earlier services attempts exposed fixture-layout issues: placing temporary repositories inside this checkout triggered the sandbox's intentional source-write denial; using macOS's default `/var` path alias failed an existing comparison with resolved `/private/var`. Both attempt logs are preserved. No services source, sandbox policy, or assertions were changed to obtain green tests.

Committed evidence:
- [Merge validation and environment details](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420/reviews/TEXTING-MERGE-0420.md)
- [Webchat tests](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420/reviews/TEXTING-0420-webchat-tests.txt)
- [Passing services tests](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420/reviews/TEXTING-0420-services-tests.txt)
- [Initial fixture-location failure](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420/reviews/TEXTING-0420-services-initial-fixture-failure.txt)
- [Temporary-path alias failure](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420/reviews/TEXTING-0420-services-temp-alias-failure.txt)

## Handoff and scope

**Offline READY for fresh LIVE Gemini + MiniMax review on `ce2482cce311ce4317c1b3aca316f1ca446aeddb`. This does not authorize deployment.** The supplied BOTH_PASS on isolated `9751346` does not transfer to this combined commit; no fresh LIVE review was run here.

Only the new draft branch was pushed. The texting source branch and clean branch were not modified. No PR was opened, merged, or undrafted; no force-push, deployment, production modification, live conductor pin change, STOP-WEBBOB change, Jeff notification, or real text message was performed. No production secrets were accessed. The existing HOLD marker was left unchanged.

The worktree has no conductor/reviews directory, so its conditional marker copy is not applicable. Committed evidence is in the worktree reviews directory.

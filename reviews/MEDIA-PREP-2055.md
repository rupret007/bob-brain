# MEDIA-PREP-2055 — OFFLINE PREPARATION ONLY / HOLD

Status: OFFLINE_PASS; clean committed candidate. Deployment HOLD. This is not a deployment, vendor review, live replay, or authorization to skip texting or gaps. Texting is still under root-agent validation; successors remain HOLD until each prior lane is deployed and accepted in sequence.

## Exact branch and ancestry

Worktree: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-media-after-texting-2055`
Branch: `draft/webbob-media-after-texting-2055` (local bob-brain Git repository)
Final candidate: `98518dc39f216fb9c4684fadc459dc54076fd48b`

| Layer | Exact commit |
| --- | --- |
| Accepted offline texting + gaps base | `fc6c719ddba680a093e28efc1a5f487dd244cf87` |
| Original media source (local conductor branch `draft/webbob-media-0927`) | `b8aa84a4f560a0b85f225a93b99981a8820a5eab` |
| Resolved media merge | `9589a37d46d0c42492f3b1c7b4351972fc4d75a2` |
| Latest texting safeguards integrated without conflict | `c63dc2fb3d3b55eaaf6c8bf00275cd64290cde6e` |
| Latest texting merged into media | `5048250c4f37cf6e42de454b75b7791ee1e071f8` |
| Media-aware Texting browser proof correction / final candidate | `98518dc39f216fb9c4684fadc459dc54076fd48b` |

The final commit contains the base, original media source, and latest texting tip as ancestors. Only this new worktree was edited. The shared texting candidate and gaps worktree were not changed. Source was fetched from the local conductor repository; nothing was pushed or activated.

## Integration decisions

- `services/api.py`: combined Gemini inline vision with the accepted explicit model selection, Google Search, reasoning configuration, metering metadata, key loading, allowed-provider checks, and 180-second reasoning-model timeout. MiniMax M2.7 remains text-only. Added a regression proving vision preserves the Pro model/search/metering options.
- `webchat/app.py`: kept the candidate-local ledger import, Texting-first routing, deep-copy public privacy projection, memory exclusions, session actor binding, captured status observations, reply authority, and hollow-progress guard. Added validated attachments, conversation-owned outbound attachment markers, media endpoints, and retained screenshot endpoints.
- `webchat/static/app.js`: preserved job-report links, captures, Texts, memory approval/dismissal, and Status-to-Jobs navigation while adding media staging/rendering. Removed an auto-merged duplicate `submitChatText` that would have replaced the media-safe helper and accidentally consumed staged attachments. Memory actions now use the same separate quick-request payload with `attachments: []`.
- Browser proof now checks the current Status navigation plus Texts quick action with no staged attachment consumption. It retains all original upload/download/playback/retry/layout/CSP checks. The provider instructions now describe the actual 32-hex media IDs and require copying the attachment snapshot ID. Two historical imported review files had trailing whitespace normalized.
- The final texting merge preserves its pure-greeting operations filter and private replay context/projection safeguards without changing them.
- Full webchat testing exposed an obsolete Texting browser readiness wait: media correctly disables an empty Send button, but the old proof waited for that button to enable before entering text. `browser_texting.cjs` now waits for the enabled composer, asserts empty Send is disabled, requires enabled Send after each fill, and uses the attachment-ready control to observe reply completion. All recipient/body, separate consent, edit/token, blocked receipt, reload, and layout assertions remain intact.

## Offline validation

All subprocesses used disposable `BOB_ROOT` directories and `/private/tmp`, with inherited KEY/TOKEN/SECRET/PASSWORD environment entries removed. Media browser proof used an ephemeral loopback server, deterministic stub providers, locally generated fixtures, and rejected every non-fixture browser request. Service tests used stubbed transports. No provider request, external project job, GitHub action, deployment, or service restart ran in this preparation.

Before final merge, focused webchat feature/Texting/gaps/status/import coverage passed 129/129, service media/worker/timeout coverage passed 21/21, and WebKit plus Chromium mobile media flows passed. One initial command included the nonexistent `test_memory` module: 102 real tests passed, but discovery failed for that mistyped name; the corrected focused command uses `test_bob_gaps` and passed. No product failure was suppressed.

The first full webchat run on `5048250` passed 466/467 and failed only the obsolete readiness wait above; the failure and initial receipt are preserved as `MEDIA-PREP-2055-initial-webchat-tests.txt` and `MEDIA-PREP-2055-initial-tests.json`. The corrected final candidate passed the complete offline suite.

Final exact-tip test receipt: `MEDIA-PREP-2055-tests.json`; every row records SHA `98518dc39f216fb9c4684fadc459dc54076fd48b`, command, duration, exit code, log path, and log digest. Logs use `MEDIA-PREP-2055-*-tests.txt`; browser screenshots are confined to `MEDIA-PREP-2055-browser-proof/` (about 604 KiB).

| Final exact-tip check | Result |
| --- | --- |
| Full webchat unittest discovery, including Texting browser proof | 467/467 PASS, no skips |
| Full services unittest discovery | 212/212 PASS, no skips |
| Bob parity evaluation | 125/125 PASS |
| Isolated replay-tool regression suite | 18/18 PASS |
| Media WebKit + Chromium mobile browser proof | PASS both engines |
| Quiet-hours JavaScript test | PASS |
| App and Texting browser proof JavaScript syntax | PASS |
| Clean worktree, all required ancestors, diff whitespace check | PASS |

Disk remained above 5 GiB (about 9.5 GiB available after preparation). The required live preflight must recheck disk immediately before a later deployment.

Browser coverage includes image/video/file upload and validated outbound echo, HEIC preview, video playback and seeking, downloads, conversation-owned drafts, idempotent retries after lost responses, progress and upload errors, Texts/Status staging isolation, 44-pixel targets, CSP, and reduced-height/landscape viewport fitting. Python coverage includes secret redaction, scope/auth/CSRF checks, symlink and malformed-input rejection, text-only provider behavior, concurrent conversation vision isolation, bounded media processing and cancellation, and preserved Texting/gaps gates.

## Release hold

The old media review artifacts imported with the source are historical and do not qualify this integrated SHA for release. Fresh source-aware MiniMax and Gemini review, exact-SHA smoke/19-turn scoped proof, authenticated rollback baseline, fresh rollback point, disk preflight (at least 5 GiB), and live replay remain required by the release owner. Root reported the latest texting c63dc2f worker probe still failed a malformed control draft; this offline result does not clear that quality hold. Texting must pass first, then gaps, then media. No API review, live visual-understanding result, BOTH_PASS, deployment, or live rollback claim is made here.

The root owner must first bring gaps forward to the final accepted texting tip. Further texting fixes, if any, must also be merged into this media branch and the affected checks rerun before fresh review. Per the root agent’s latest instruction, no new lane merges should start until a further root message; Instinct/voice preparation remains paused even after this report is complete. No deployment order advances.

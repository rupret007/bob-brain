# Web Bob voice offline fixes — 2026-09-28

RESULT: **OFFLINE_PASS**

Reviewed code tip SHA: `c5d7addcb90a25e38fff3b301de3cfdc19b40f81`.
Branch: `draft/webbob-voice-fix-1008`, based on the existing remote voice draft
`8e2996c207b88500330f5ee0d7e86eaf002259f4` (`draft/webbob-voice-0927`, draft PR #9).
The subsequent evidence commit changes only this report and test logs. The
operational `conductor/reviews/VOICE-FIXED-1008.md` records the final pushed tip
and draft PR URL.

This is an offline regression and source review against the findings in
`conductor/reviews/WEBBOB-VOICE-MINIMAX-0927.md`. It is not a fresh vendor verdict
or evidence that live voice works on a physical device.

## Review findings addressed

| Finding | Change and offline evidence |
| --- | --- |
| BUG-1 | Removed the indexed/sliced `new_messages` bridge. The saved voice user row is reused and an explicit assistant row is appended. The minimal voice-turn test verifies exactly one user, one reply, and no duplicate dispatch on retry. |
| BUG-2 | `sweep_stuck()` prefers the pinned `reply_id`, then falls back to `messages[-1]` for an absent/stale ID. Tests cover both fallbacks, a pinned reply followed by newer speech, persistence, and empty history. |
| BUG-3 | Voice reply ordering uses `source.get("voice_order", 0)`; transcript sorting also accepts legacy rows missing that field. A legacy transcript can dispatch and save subsequent speech. |
| SEC-1 | All five voice POST endpoints already pass through the same authenticated CSRF check as text. `test_voice_csrf_required` explicitly rejects missing, empty, incorrect, and another login's CSRF token on start/transcript/tool/end/pulse, before the handler can mutate state. Existing origin/Host and authentication checks remain covered, now including unauthenticated pulse. |
| SEC-2 | Token creation is capped at 10 attempts per rolling minute per login and 20 across the application's single owner's logins. Reservations happen under the chat lock before provider work, and failed attempts count. Hangup/logout cannot refund attempts. Tests cover HTTP 429, repeated cancellation, provider failure, session rotation, the minute boundary, and simultaneous starts while token creation is in flight. Limits are process-local and use monotonic time. |
| SEC-3 | Invalid voice-source `RequestError` is now generic. Missing voice credentials also return a generic availability message rather than revealing the credential variable and filesystem layout. |

Voice start now checks all pending replies, so a late transcript cannot hide
queued work. A waiting reply behind newer speech also blocks another submission,
and Stop cancels that reply without overwriting the speech. Safari's paused
state survives incoming events and successful save retries; a late Resume
promise cannot overwrite the ended-call state.

## Required scenarios

| Test | Coverage |
| --- | --- |
| TEST-1 | Concurrent transcript writes versus typed messages are isolated; a simultaneous voice-start/text-submit race admits exactly one operation. |
| TEST-2 | Mocked clock checks an abandoned lease at 44.999 and exactly 45 seconds, rejects stale pulse/tool work, permits final transcript flush, and recovers the slot without ending the other call. |
| TEST-3 | A regularly renewed call expires at ten minutes. Server tool/pulse requests receive 410, final speech saves, and restart is explicit. Fake browser timers verify socket/microphone/audio/timer cleanup and interrupted transcript saving without automatic token refresh. |
| TEST-4 | A held tool is interrupted while in flight. Replayed requests do not dispatch twice, an old transcript write cannot remove interruption marking, cancelled tool output cannot speak later, failed transcript writes retry, and a subsequent spoken turn can proceed. Thread events/deferred promises avoid real-time sleeps and real providers. |
| TEST-5 | A suspended Safari AudioContext cannot send microphone packets. Provider events and save completion preserve Resume audio until an explicit resume; late resume after hangup is ignored. |
| TEST-6 | Voice start rejects queued, running, and provider-cooldown replies before minting a token. Cancellation permits a new call, including when a late transcript follows the pending reply. |

## Verification

All providers, sockets, AudioContexts and media tracks in these tests are fakes
or mocks. HTTP security tests use an ephemeral loopback listener with private
fixture data. No proof server or live-audio harness was run.

| Check | Result | Evidence |
| --- | --- | --- |
| Entire Python webchat suite | **270 passed** (baseline 254; 16 added) | [log](voice-fixed-1008/webchat-tests.txt) |
| Voice Python subset, included above | **34 passed** | [log](voice-fixed-1008/voice-tests.txt) |
| Entire Python services suite | **111 passed** | [log](voice-fixed-1008/services-tests.txt) |
| Voice JavaScript / AudioWorklet suite | **22 passed** (baseline 18; 4 added) | [log](voice-fixed-1008/voice-js-tests.txt) |
| Quiet-hours JavaScript regression | **Passed** | [log](voice-fixed-1008/quiet-hours-js-tests.txt) |
| Syntax / whitespace | **Passed**: `node --check` for `voice.js`, `voice-capture.js`, `app.js`; `git diff --check` | [source hashes](voice-fixed-1008/source-sha256.txt) |

The newly added tests reproduced timeout fallback failure, missing legacy
ordering, unbounded token issuance, architecture disclosure, hidden waiting
replies and Safari state regressions before the implementation fixes. Other
requested scenarios confirmed existing behavior under explicit offline coverage.

Reproduce from this worktree:

```sh
mkdir -p .voice-work/tmp
BOB_ROOT="$PWD/.voice-work/root" TMPDIR="$PWD/.voice-work/tmp" PYTHONPATH="$PWD/state" \
  python3 -m unittest discover -s webchat -p 'test_*.py'
BOB_ROOT="$PWD/.voice-work/root" TMPDIR="$PWD/.voice-work/tmp" \
  python3 -m unittest discover -s services -p 'test_*.py'
node --test webchat/test_voice_js.cjs
node --test webchat/test_quiet_hours_js.mjs
node --check webchat/static/voice.js
node --check webchat/static/voice-capture.js
node --check webchat/static/app.js
git diff --check
```

## Live review status

**SKIPPED_LIVE_REVIEWS** — the latest available live-review receipts for texting
tip `1ca5e12e06c9352ebf38005bcf8e764d03307c3b` show Gemini HTTP 402 and MiniMax
timeout (`HTTP 0 curl_rc=28`, after the previously reported empty response).
These are the 2026-09-28 14:33–14:36 UTC attempts recorded in operational
`conductor/reviews/TEXTING-LIVE-0916.md`,
`LIVE-GEMINI-draft_webbob-texting-diagdump-fix-0916-1ca5e12-0916-attempt2.md`, and
`LIVE-MINIMAX-draft_webbob-texting-diagdump-fix-0916-1ca5e12-0916-attempt2.md`.
Jeff explicitly authorized skipping these unavailable review lanes. No fresh
provider request was made and no current availability or BOTH_PASS claim is
made for this voice tip.

No Grok/xAI, phone calls, live audio, Jeff notifications/texts, deployment,
force-push, merge, or texting deployment changes. Live/physical-device voice
verification remains outstanding until Jeff is present. The existing texting
NOT_BOTH_PASS deployment blocker remains untouched.

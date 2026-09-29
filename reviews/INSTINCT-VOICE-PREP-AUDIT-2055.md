# Instinct / voice offline preparation audit — 2055

Status: **AUDIT ONLY; DEPLOY HOLD.** No feature merge, provider/API call, push,
activation, or test execution was performed by this audit. Source worktrees were
clean. The current user order is texting → gaps → media → Instinct → voice → UI;
older lane reports specify a different order and do not override it.

Compared against gaps `fc6c719` and media preparation `5048250c4f37cf6e42de454b75b7791ee1e071f8`
(parents: media/gaps `9589a37`, current texting `c63dc2f`). Media subsequently
advanced to `98518dc39f216fb9c4684fadc459dc54076fd48b`, changing only
`webchat/browser_texting.cjs` readiness waits. The media preparer reports final
exact-tip webchat 467/467, services 212/212, parity 125/125, replay tools 18/18,
WebKit/Chromium media browsers and JS checks passed; see `MEDIA-PREP-2055.md`.
No new merge is authorized while the current texting release is held.

## Instinct: additive, with evaluation conflicts

- Tip: `c51860cc36be4c44be722ba8175095b625666c4f`, branch
  `draft/webbob-instinct-0810`, worktree `workspaces/webbob-instinct-0810`.
  Product commit is `34fc05ee5bdf89a8345c8a5602c761e37f97878d`; final tip changes
  only whitespace in a preserved failure log. Parent `1d72c44` includes texting
  `ce2482c`; merge base with current media is
  `ce2482cce311ce4317c1b3aca316f1ca446aeddb`.
- The feature delta is 15 files, 916 insertions / 1 deletion, mostly new
  `instinct.py`, fixture, 31 tests, 22-case evaluation, docs and historical logs.
  Only nine lines hook it into `texting.py` (initialization, exact Instinct
  resolver, tagged draft body, command handler). It adds no provider, service,
  `app.py`, or browser implementation. Current media's `texting.py` still matches
  this merge base, so those hooks apply without replacing the current app.
- Behavior: BlueBubbles-backed, owner-requested latest replies/read/digest;
  explicit or local-template drafts tagged `[Bob via Andrea]`. Exact verified
  single-recipient resolution, bounded excerpts, untrusted incoming content,
  no automatic replies, and existing actor/exact-token consent remain. No actual
  production Instinct mapping or message delivery was verified.
- Read-only three-tree comparison found conflicts in `webchat/README.md`,
  `bob_parity_eval.py`, and `test_webchat.py`. Retain media docs and all current
  125 parity cases, then append the 22 Instinct cases: expected total **147** if
  no other cases change. Do not accept the old branch's total of 118 or replace
  the current guard/worker cases with the Instinct-only hunk.
- Historical evidence: [INSTINCT-FIXED-0810.md](INSTINCT-FIXED-0810.md) and
  [INSTINCT-LIVE-0810.md](INSTINCT-LIVE-0810.md): 411 webchat passed, one optional
  Playwright skip, 131 services, Instinct 22/22, parity 118/118, both reviewers
  passed the old exact tip. These are not results for an integrated 2055 tip.

## Voice: old base, substantive integration blockers

- Tip: `5ff8b606b2a60544d83367a81ffd78e4212ec7ff`, branch
  `draft/webbob-voice-fix-1008`, worktree `workspaces/webbob-voice-1008`.
  Product fix commit `c5d7addcb90a25e38fff3b301de3cfdc19b40f81` follows
  `8e2996c` (merge of original voice `cf46be9` with UI `7ab7f13`). Final tip adds
  reports/logs only. Merge base with current media and Instinct is
  `7ab7f1311f70262932a9e8dcc7f78c096e996567`.
- Relative to that base: 45 files, 3,703 insertions / 197 deletions including
  historical screenshots/logs. Core additions are `voice.py`, `voice.js`,
  `voice-capture.js`, HTTP/tool integration, pinned reply rows, transcript order,
  token/lease limits and browser controls. `job_queue.py` adds spoken comma/period
  separators. `services/test_services.py` adds fixture-path isolation; it does
  not change production acceptance.
- Three-tree comparison against media found conflict markers in `.gitignore`,
  `webchat/app.py` (five regions), `static/app.js`, and `static/index.html`.
  Other changed-in-both files auto-combine but still need review. Preserve
  current actor and attachment arguments, source-local ledger import, texting
  interception, status observation/repair, dispatcher authority, memory/media
  controls, and a single `submitChatText` binding. Layer voice's `source_voice`
  and pinned reply rows into those paths; do not replace them with the old app.

Confirmed integration issues that require fixes and regression coverage before
voice can pass current requirements:

1. **Private texting / Instinct context would reach Gemini.** `voice.py:148–151`
   directly copies saved messages into token setup. Current `app.py:796` filters
   provider input through `texting.provider_view()`. Voice must preserve that
   boundary too. Separately, `static/voice.js:207–219` sends the selected
   `ask_bob` answer's content as a Gemini tool response without checking its
   `texting` flag; a read/digest result could leak even with startup filtering.
   Test both boundaries with unmistakable private content and consent tokens.
2. **Authenticated draft ownership is absent from the old bridge.**
   `voice.py:234` calls `chat.submit(..., source_voice=source_id)` without actor.
   Current `texting.py:250–252` correctly refuses drafts without an actor.
   Define and test intended authenticated voice behavior when integrating the
   signature; keep actor matching and separate exact-token consent intact.
3. **Browser receipt assertion is stale.** `voice_browser_proof.cjs:152,161`
   requires case-sensitive `/Queued/`; current `task_dispatch.py:115` emits
   `I queued …`. Correct the wording match while retaining actual dispatcher,
   task ID, durable receipt, tool acknowledgement and audio assertions.
4. **Proof evidence is tied to an old directory.** The voice browser script
   hardcodes `reviews/webbob-voice-0927` at line 13. Give any future 2055 run a
   bounded per-attempt output directory; preserve old evidence and disk floor.

Historical [VOICE-FIXED-1008.md](VOICE-FIXED-1008.md) reports 270 webchat,
34 voice Python, 111 services and 22 voice JavaScript tests passed. Its verdict is
**OFFLINE_PASS / SKIPPED_LIVE_REVIEWS**, not BOTH_PASS. Those tests use mocked
providers/audio. Earlier browser receipts do not cover the final fixes, current
merge, or a physical iPhone microphone.

## Validation entry points for a future integrated tip

Run all with isolated fixture data, canonical `/private/tmp`, current checkout's
`state` on `PYTHONPATH`, and no live service/pin mutation. These commands were
inspected, not executed by this audit:

```sh
TMPDIR=/private/tmp python3 -m unittest discover -s webchat -p 'test_*.py'
TMPDIR=/private/tmp python3 -m unittest discover -s services -p 'test_*.py'
node --test webchat/test_voice_js.cjs
node --test webchat/test_quiet_hours_js.mjs
node webchat/test_job_results_js.mjs
node --check webchat/static/voice.js
node --check webchat/static/voice-capture.js
node --check webchat/static/app.js
```

Instinct's `webchat/instinct_eval.py` runs 22 offline synthetic cases; broader
`bob_parity_eval.py` includes them. Their CLI entry points write evidence, so use
a bounded output arrangement. `test_instinct.py` includes authenticated loopback
read/digest/draft/separate-yes coverage. It has no dedicated Instinct browser
harness. Existing `texting_proof.py --output-dir <private-directory>` uses
synthetic threads and requires installed Playwright; an optional skip is not
fresh browser proof. Preserve media WebKit/Chromium and texting card checks.

The voice proof is deliberately **live**, not an offline test:
`python3 webchat/voice_proof_server.py --data <private-child-of-worktree>` starts
an isolated server. `--keys` copies only the Gemini credential and removes it on
normal shutdown. `BOB_VOICE_PROOF_ROOT` points to its `server.json` directory,
`BOB_VOICE_FIXTURES` needs question-short/story/interrupt/tool WAV files, and
`BOB_PLAYWRIGHT_MODULE` selects installed Playwright.
`node webchat/voice_browser_proof.cjs` selects Chromium; `--webkit` selects
WebKit. Optional `BOB_VOICE_PROOF_URL` targets the isolated HTTPS proxy.
The harness uses synthetic microphone input with real Gemini audio/tool traffic;
it checks queued work, not completion by real workers. It must not substitute
for the required named-worker and live replay gates.

Current texting hold classification: receipt
`TEXTING-WORKER-2055-20260928-213810/receipt.json` has a genuinely incomplete
MiniMax result. Its second regression case has only name/target/setup; required
action/expected are buried inside the setup string. Exact prompt lines 13 and
1125 explicitly prohibit this and show both complete field sets. The corrected
fixture is absent as disclosed, not partially leaked. `api_worker.py:215–217`
correctly rejects the missing outer fields. No remaining tooling/input defect
was demonstrated for this result; no acceptance weakening or prompt fishing is
justified by it.

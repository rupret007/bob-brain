# Web Bob voice parity — 2026-09-27

Branch: `draft/webbob-voice-0927`. PR target: **`draft/webbob-clean-0927`**, draft only.

Read `/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/WEBBOB-PARITY-0927.md` before implementation. All implementation, fixtures, private server data and screenshots live in this worktree. No production service was changed, stopped, restarted or deployed; no existing tailnet serving configuration was changed. The proof servers do not start workers, provider probes or service supervisors. The test jobs remain queued only in private fixture roots.

## Result

The waveform immediately right of the composer microphone starts a streaming, two-way call. The microphone button remains dictation. Live voice has native spoken output, automatic barge-in, a large Hang up button, live captions, a saved chat transcript, microphone-denial recovery and Safari audio-resume handling. The waveform target is 44 × 44 pixels at the 390 × 844 phone viewport, with no horizontal overflow. Leaving the page ends the call.

The specified key file contains `GEMINI_API_KEY` and no OpenAI credential. This lane uses **Gemini Live (`gemini-3.8-live`)**, the authorized Realtime equivalent, through the existing Gemini credential. No Grok/xAI service is used. A real model-list request confirmed Live availability, and real constrained-token creation and audio sessions succeeded. The permanent key stays on the server. Each browser token allows one session, expires after ten minutes, and locks the model, voice, instructions and tools. The Python application remains standard-library-only.

The implementation follows Google's [Live WebSocket protocol](https://ai.google.dev/gemini-api/docs/live-api/get-started-websocket), [ephemeral token contract](https://ai.google.dev/gemini-api/docs/live-api/ephemeral-tokens), and [interruption events](https://ai.google.dev/api/live). Microphone audio is resampled to mono PCM16 at 16 kHz in 100 ms AudioWorklet packets; generated PCM audio is scheduled with Web Audio. An interruption stops and discards all queued output immediately.

## Chat parity and persistence

Voice receives the same redacted profile, handback, status and recent conversation context as chat. Its `ask_bob` tool takes no model-authored command arguments: the server dispatches the **saved spoken transcript** through `Chat.submit`. Existing task routing, draft-only rules, memory behavior and action receipts apply. Request IDs are deterministic per spoken turn, so replaying a tool request does not queue another job. Recognition punctuation such as “Start a job, write tests” is now accepted by the shared parser without rewriting the saved request.

Transcripts are saved during the call in the existing private conversation files. Versioned writes prevent an older network response from replacing newer words; message identity prevents duplicate transcript bubbles on retries. The original server tool receipt and the spoken paraphrase both remain available. A tool worker pins its input context and updates its own reply ID, so a later utterance cannot replace either its input or its result. Interrupted output is marked; generated transcripts can include words that were not played.

Voice endpoints retain session authentication, origin/Host checks and CSRF protection, and calls belong to the login session that created them. There are at most two active calls, a 45-second renewable lease for abandoned tabs, a ten-minute token lifetime, and no automatic call restart. Hangup closes microphone tracks, playback nodes, the AudioContext and the provider socket before awaiting transcript writes. Hangup sends the server release immediately even if saving is delayed. Failed transcript writes offer Retry save; unsaved audio is not recorded for later transcription. Interrupting audio does not undo an already authorized, queued job.

## Verification

| Check | Result | Evidence |
| --- | --- | --- |
| Entire Python webchat suite | **186 passed** | [test log](webbob-voice-0927/webchat-tests.txt) |
| Entire services suite | **111 passed** | [test log](webbob-voice-0927/services-tests.txt) |
| Voice JavaScript / AudioWorklet tests | **17 passed** | [test log](webbob-voice-0927/voice-js-tests.txt) |
| Syntax and whitespace | Passed: JS syntax checks and `git diff --check` | Commands below |
| Chromium + real Live API | Passed: input/output audio, memory, barge-in, actual dispatcher receipt, hangup cleanup, reload, denied microphone | [receipt](webbob-voice-0927/chromium-proof.json) |
| WebKit 26 + real Live API | Passed with an iPhone viewport; same call scenarios | [receipt](webbob-voice-0927/webkit-proof.json) |

The tests cover authentication, call ownership, constrained credentials, transcript ordering/redaction/replay, immutable dispatched requests, stale transcript versions, abandoned-call leases, pinned tool context, late microphone/token promises, permission denial, transport backpressure, cancelled tools, output interruption, Safari suspension, delayed-save hangup, and resampling at 16/44.1/48 kHz. The services test fixture now points its sandbox at its own core, allowing its real commit/push boundary test to run with `TMPDIR` inside this worktree; production sandbox behavior is unchanged.

The final proof instance is **`https://jeffs-mac-mini.tail758ab4.ts.net:54445`**, with a separate loopback HTTP listener and private data under `.voice-work/review-root`. Its certificate/key were written to ignored files in this worktree with `tailscale cert`; no `tailscale serve` command was run. This is a spare-port test instance, not the production URL. The private proof login is in `.voice-work/review-root/conductor/webchat/.password`; it is not committed or printed in evidence.

Proof input is reproducible speech synthesized locally with macOS `say`, passed through a browser MediaStream and the production AudioWorklet. The provider connection, incoming audio, returned speech, playback scheduling, interruption event, tool dispatch and transcript persistence are real. An additional Chromium run exercised its native fake microphone capture API; see [native capture screenshot](webbob-voice-0927/live-mic-iphone-chromium.png). No physical microphone/speaker or physical iPhone was available to this runner. **Physical iPhone Safari permission prompts, speaker routing, echo cancellation and screen-lock behavior still need a device check before deployment.** Earlier WebKit harness failures came from its replaceable MediaDevices wrapper; the proof now injects synthetic input on the prototype and keeps the application's CSP enforced.

## Screenshots

| Phone | Desktop |
| --- | --- |
| [Composer / waveform placement](webbob-voice-0927/chromium-iphone-composer.png) | [Live call](webbob-voice-0927/chromium-desktop-call.png) |
| [Listening](webbob-voice-0927/webkit-iphone-listening.png) | [Saved transcript](webbob-voice-0927/chromium-desktop-saved-chat.png) |
| [Safari-engine memory answer](webbob-voice-0927/webkit-iphone-memory.png) | [Safari-engine call](webbob-voice-0927/webkit-desktop-call.png) |
| [Interrupted speech](webbob-voice-0927/webkit-iphone-interrupted.png) | [Safari-engine saved chat](webbob-voice-0927/webkit-desktop-saved-chat.png) |
| [Microphone permission recovery](webbob-voice-0927/webkit-iphone-permission.png) | |

## Reproduce without production services

Run from this worktree. Keep all test data inside an ignored private folder:

```bash
mkdir -p .voice-work/tmp
BOB_ROOT="$PWD/.voice-work/root" TMPDIR="$PWD/.voice-work/tmp" PYTHONPATH="$PWD/state" \
  python3 -m unittest discover -s webchat -p 'test_*.py'
BOB_ROOT="$PWD/.voice-work/root" TMPDIR="$PWD/.voice-work/tmp" \
  python3 -m unittest discover -s services -p 'test_*.py'
node --test webchat/test_voice_js.cjs
node --check webchat/static/voice.js
node --check webchat/static/voice-capture.js
node --check webchat/static/app.js
git diff --check
```

For a new isolated server, choose an unused tailnet port, an unused private data directory, and a certificate/key stored inside this worktree:

```bash
python3 webchat/voice_proof_server.py \
  --data .voice-work/new-proof-root \
  --keys /Users/jeffstory/Documents/bob-overnight-inject/conductor/keys.env \
  --origin https://jeffs-mac-mini.tail758ab4.ts.net:SPARE_PORT \
  --tailnet-ip 100.67.108.113 \
  --tls-cert .voice-work/tailnet.crt --tls-key .voice-work/tailnet.key
```

Generate mono 16 kHz WAV fixtures with `say -v Samantha -o <name>.aiff '<text>'` followed by `afconvert -f WAVE -d LEI16@16000 -c 1 <name>.aiff <name>.wav`. The browser proof expects `question-short.wav` (ask the test sailboat's color), `story.wav` (ask for a long sailing story), `interrupt.wav` (“Stop. Say only, okay Jeff.”), and `tool.wav` (“Start a job: write unit tests for a pretend blue widget.”).

Set `BOB_PLAYWRIGHT_MODULE` to an installed Playwright package, `BOB_VOICE_PROOF_ROOT` to the new private data root, `BOB_VOICE_PROOF_URL` to its HTTPS URL and `BOB_VOICE_FIXTURES` to that WAV directory. Run `node webchat/voice_browser_proof.cjs`, then repeat with `--webkit`. The completed proofs used Chromium 143 and WebKit 26.0; browser binaries and npm dependencies were kept in or read from test caches. No application runtime dependency was added.

Keep the PR in draft. No merge, undraft or deployment is part of this lane.

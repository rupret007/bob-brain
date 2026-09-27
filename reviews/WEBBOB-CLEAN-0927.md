# Web Bob clean chat — 2026-09-27

PASS. Ordinary chat has no job disclaimer or command-syntax footer. Natural work requests create real durable jobs, then receive a short server-owned receipt. Ambiguous requests get one question. No live service was restarted or deployed.

Target: `brain` branch `draft/webbob-clean-0927`; DRAFT PR on `rupret007/bob-brain`, base `draft/webbob-minimax-0927` (`855be8b5c9056e4f8d356b958cf6f136504d1ddb`).

## Behavior

- `fix X`, `review PR #161`, and `have Claude do Y` dispatch through `task_queue.enqueue`, including polite and conversational prefixes. Chat preferences and negated requests remain chat.
- `go` and `please go ahead` accept one clear current saved proposal, including natural offers such as “I can offer to take a look at …”. Missing context, multiple options, old context, and a repeated “go” after dispatch ask “What would you like me to work on?” without creating a job.
- The server saves intent, then writes the locked/fsynced queue journal before returning a job ID. A queued task says “Queued — job ….” or “Queued for Claude — job ….”. Only a persisted worker claim changes the receipt to “Started on Claude — job ….”. A model answer cannot create these receipts.
- Unsupported model claims and no-job notices are removed without adding a footer or flattening the useful answer's paragraphs. Casual chat does not turn a stray provider claim into an unsolicited status report. Explicit status requests still use server data.
- Existing retry, duplicate-request, crash recovery, legacy proposal IDs, result acceptance, capability checks, and forbidden-worker protections remain covered. Polite file requests retain their required file-capable worker routing.

## Final full-suite validation

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **170 passed**, 16.553 s |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed**, 4.444 s |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `python3 bootstrap.py check` | **syntax: PASS** |
| `git diff --check` | **Passed** |

No tests were skipped. The first chat run exposed two fixtures that still expected ambiguous “do it” to invent a default job; they now seed a saved legacy proposal to retain the original persistence and stale-card assertions. That run also hit a transient macOS process-group PermissionError; the complete final suite, including real child-process cancellation, passed. Service-test “restarted svc-reviewer” lines come from mocked watchdog tests.

## Six isolated live examples

The proof used a new temporary data root and an ephemeral loopback HTTP server. It authenticated through `/login`, obtained a CSRF token, submitted `/api/messages`, polled conversation replies, and checked `/api/jobs` against the actual durable queue journal. The ordinary answer and setup proposal used real Claude generation, with no provider mocks. The four work requests used the normal server dispatch handler, with no direct queue injection.

| # | Message | Actual reply | Queue rows for this request |
| --- | --- | --- | ---: |
| 1 | Keep replies short and friendly. | Got it. | 0 |
| 2 | fix the login button | Queued — job webchat-3ebcec3d42fa53d8960280dab174a40d. | 1 |
| 3 | review PR #161 | Queued — job webchat-4024dee1e0ee545b8149d07967a4b68b. | 1 |
| 4 | have Claude review PR #161 | Queued for Claude — job webchat-2a5cffd7bb2458c8bfbbdb0a202c77a2. | 1 |
| 5 | go (new conversation) | What would you like me to work on? | 0 |
| 6 | go (after the proposal below) | Queued — job webchat-5c38f8fb4d5a52ca8f4a0ce91dfd6939. | 1 |

Example 6 followed this actual setup exchange in the same conversation:

> Jeff: Can you offer to review PR #162 in one short sentence?
>
> Bob: I can take a look at PR #162 if you want — just say the word.

The proof ran **2026-09-27T18:46:03.353191+00:00 → 2026-09-27T18:46:15.299124+00:00**. Every example produced one short line. All four job receipts matched their journal's conversation ID, request ID, requested worker, and task ID. Four HTTP retransmissions returned the same receipts and left exactly four jobs. The ordinary instruction, setup proposal, and ambiguous “go” had no job rows.

No worker runner was started in this isolated proof: all four tasks remained `queued`, with zero attempts and no claimed worker. This proves authenticated chat behavior and durable job acceptance, without claiming that the requested fixes or reviews executed. The running-receipt transition and failure honesty are covered by the automated queue tests.

The live listener stayed **PID 99149**, started **Sun Sep 27 12:40:03 2026**, before and after the proof. Service screen identities were also unchanged. Live queues, conversations, service locks, deployment pins, and running code were untouched. No merge, force-push, or Grok invocation occurred.

The [raw evidence](WEBBOB-CLEAN-0927.evidence.json) contains all six exchanges, the proposal, real queue events, replay counts, listener/screen identities, and SHA-256 hashes matching the final implementation and proof runner. The first isolated attempt revealed an unrecognized natural Claude proposal; a regression now covers that wording and the final proof passed.

Reproduce from the checkout with the existing Claude CLI login:

```sh
python3 webchat/live_clean_proof.py --provider claude --output reviews/WEBBOB-CLEAN-0927.evidence.json
```

The [proof runner](../webchat/live_clean_proof.py) allocates its own data root, password, sessions, queue and listener, and closes only that listener when finished. It leaves a private `proof.json` in the temporary root as well as the requested evidence file. It never starts or restarts the live web service or scheduler.

## Follow-up: project dispatch and explicit holds

PASS. This follow-up addresses the final exchanges in `conductor/webchat/sessions/2bd59fcd-cb1d-40e5-adcf-2da66824ec88.json`: the project order was supplied in one turn, then “Now push everything to the max and fix anything you find along the way” received agreement without jobs and an obsolete hold reminder.

The chat now persists project priorities and permission transitions. That request creates exactly one durable job for each named project, with a short server-owned receipt listing project, worker and job ID. Each assignment contains only its own project's name so the existing worker's repository selector cannot pick another project. Worker choice considers ready lanes, queue claims and pending assignments, while retaining existing capability limits: coding runs on Codex/Cursor; supplied-evidence analysis can spread across the other model workers. No scheduler, worker executor or queue schema changed.

Explicit holds block new matching chat submissions. `go`, `resume`, and an explicit hold-lift directive clear the relevant saved hold; an explicit project push authorizes those projects. Held work survives reloads and unrelated project submissions. Old sessions replay only user permission/priority directives into state, without dispatching historical messages. Saved state is included in provider context and checked again when replies are delivered, so stale assistant text cannot restore a cleared hold. Holds do not cancel jobs already accepted by the queue or restart services.

### Full-suite validation

| Command | Final result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **190 passed**, 13.395 s |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed**, 2.484 s |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `python3 bootstrap.py check` | **syntax: PASS** |
| `git diff --check` | **Passed** |

The 20 new regressions cover the exact two-turn request, inline project lists, aliases/exclusions, worker headroom and capability checks, actual queue claims updating receipts, interrupted batch writes, stable recovery plans, failed state writes, scoped/global holds, resume after reload, legacy session migration, negated/quoted requests, and stale model permission claims. Existing max-mode syntax remains covered; a full-suite run exposed a resume-prefix conflict with “Go to the max,” which was fixed before the final passing run. No tests were skipped. Service restart log lines come from mocked watchdog tests.

### Isolated HTTP proof

The [follow-up proof runner](../webchat/isolated_intent_proof.py) creates a fresh temporary root and ephemeral loopback listener. It authenticates, uses CSRF-protected `/api/messages`, checks `/api/jobs` against the actual `conductor/state/queue.jsonl`, and reloads only its private Chat instance. No worker runner or external model was started. One deliberately stale provider fixture exercises the final reply filter; this proof does not claim live model generation or execution of the queued project work.

The exact hold and priority messages were submitted first. The push then produced this actual receipt:

```text
Web Bob: Queued for Codex — job webchat-fb654cbb485c5ee38c026b285dc75069.
WebJam: Queued for Cursor — job webchat-fb981204170556f386f879574f06d6b6.
AdoptIQ: Queued for Codex — job webchat-53155362fcfe5d15b4dd4d5564c82ca6.
StoryBoard: Queued for Cursor — job webchat-886385387ae5533ea93289bbbd9f80e7.
```

All four rows were `queued`, with zero attempts and no claimed worker. Four private state reloads and three HTTP retransmissions preserved the job IDs without duplicates. A later Web Bob hold blocked a new login job; `resume` created exactly that one additional job and persisted the cleared hold. Repeating a bare `go` after the project batch created no jobs. The injected “Your earlier hold … still applies. I need your permission …” reply became “Ready when you are.”

The proof ran **2026-09-27T19:15:58.110059+00:00 → 2026-09-27T19:15:58.736167+00:00**. Its [raw evidence](WEBBOB-CLEAN-0927.followup-evidence.json) contains the exchanges, saved states, five real enqueue events, API rows, source hashes, and queue SHA-256 `e53c0ab6819ea64a16927ae7561d6d50549d48d0d80ae589383c85c723b747f5`. Source hashes were verified against the final implementation.

The live listener remained **PID 99149**, started **Sun Sep 27 12:40:03 2026**, and service screen identities were unchanged. Live queues, sessions, processes and deployment pins were untouched. No live restart, merge, force-push or Grok invocation occurred.

```sh
python3 webchat/isolated_intent_proof.py --output reviews/WEBBOB-CLEAN-0927.followup-evidence.json
```

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

## Follow-up 3: live workers and plain status

PASS. Read the last four messages in Jeff's session `2bd59fcd-cb1d-40e5-adcf-2da66824ec88`. The old status counted only queue claims, classified unmatched `lane-*` screens as “other,” and missed “Ok great is it moving along now?”. Its default formatter also exposed provider internals, old job IDs and `None` worker values.

Status now joins the queue with read-only `screen -ls` and `ps` observations. It follows screen descendants through login/shell/CLI wrappers, includes standalone CLI workers and verified dispatch processes, and counts a queue claim and its observed worker once. Each active item shows its task label, actual worker, explicit model argument when available, and elapsed process time. Process evidence overrides cached “ready” lane states. Screen names do not determine the model: the MiniMax-fix lane in the reproduction correctly runs on **Codex**.

Open screens without an observed worker stay unverified. Stopped workers are reported as paused, zombies and desktop app helpers are excluded, and unavailable process/screen checks cannot produce an idle claim. Task labels come from queue titles/projects or readable lane names; raw process prompts and claim tokens never enter the snapshot. Model variants and unknown task details are not guessed. A running process establishes activity, not successful forward progress or completion. Reading a stale dashboard now skips the ledger-writing inline refresh.

The exact progress question uses the server status path without a model call or queue write. Default replies omit internal IDs, screen names, old-job history, health-file names and null values. Explicit requests can reveal identifiers and health in readable text; a request to omit those details keeps them hidden. Provider instructions agree with the formatter, and the final reply guard removes special job-syntax advice regardless of whether it says “type,” “submit,” or “use.” Natural work requests retain their existing dispatch behavior. The earlier hold-lift message now receives “Ready when you are.” and creates no duplicate project jobs.

### Validation

| Command | Final result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **206 passed**, 13.061 s |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed**, 2.542 s |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `python3 bootstrap.py check` | **syntax: PASS** |
| `python3 -m py_compile` on the new collector/proof and changed status modules | **Passed** |
| `git diff --check` | **Passed** |

The 16 added regressions cover the four-lane/empty-queue case, screen ancestry and duplicate wrappers, actual worker/model/elapsed metadata, standalone workers, desktop helpers, paused/zombie/disappeared workers, API dispatch processes and reused PIDs, unavailable checks, prompt-budget retention, stale-dashboard read-only behavior, hidden/requested identifiers, syntax advice, and authenticated status without duplicate dispatch. Existing tests that required the raw provider/footer dump were updated to require plain replies. No tests were skipped. Service-suite restart log lines come from mocked watchdog tests.

### Authenticated HTTP proof

The [proof runner](../webchat/isolated_status_proof.py) used a fresh temporary data root and ephemeral loopback server, authenticated login and CSRF-protected `/api/messages`. It reproduced the original four screen names with deterministic process fixtures and an empty dispatch queue. **The four workers, durations and model flags below are fixtures, including the synthetic `gpt-fixture` model; no model or worker was launched by the proof.**

For both “Ok great is it moving along now?” and “status,” the actual HTTP reply was:

```text
Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.

Nothing else is waiting in the queue.
```

The proof also requested screen names, job IDs and PIDs explicitly; only that reply included them. All default replies excluded `Answering provider:`, `History:`, `None`, internal IDs and the obsolete syntax advice. There were **zero provider calls, zero dispatch jobs and no dispatch journal created**.

A separate **actual read-only host observation**, passed through the same isolated HTTP handler, found one running worker (`lane-webbob-clean3`, Codex, process age 1,106 seconds), an open `lane-webbob-ui` session with unconfirmed worker activity, and zero queue claims. Its reply reported that work plainly instead of treating the empty queue as inactivity. This later observation does not claim the original four sessions were still running.

The final proof ran **2026-09-27T19:37:48.266820+00:00 → 2026-09-27T19:37:48.919491+00:00**. The [evidence](WEBBOB-CLEAN-0927.status-evidence.json) contains both fixture and actual observations, HTTP replies, inspection availability, zero-call/zero-job checks and verified SHA-256 hashes of the final implementation and proof sources.

The live listener remained **PID 99149**, started **Sun Sep 27 12:40:03 2026**; all seven service screen identities matched before and after. No live service restart, deployment, merge, force-push or Grok invocation occurred. The proof closed only its own isolated listener.

```sh
python3 webchat/isolated_status_proof.py --live-root .. --output reviews/WEBBOB-CLEAN-0927.status-evidence.json
```

## Follow-up recheck: project jobs and current holds

PASS. Re-read Jeff's session and verified the project dispatch and explicit permission changes already on this draft branch. The exact priority-then-push request still creates one real `conductor/state/queue.jsonl` job per project, with project, assigned worker and job ID in a four-line server receipt. Existing coverage checks compatible worker capacity, active claims, pending assignments, recovery and duplicate requests.

This recheck fixed three remaining cases in chat intent, saved permissions and replies:

- A named confirmation such as “Go ahead with Web Bob, WebJam, AdoptIQ and StoryBoard” now accepts the matching saved project plan. A project-specific resume accepts only a current task wholly within the named scope; it cannot dispatch unrelated held work or replay an already accepted plan.
- A push with no resolved projects previously cleared saved holds while asking which projects to use. It now preserves both the hold and the last permission transition, including when exclusions remove every target.
- Provider claims such as “Web Bob is paused until you say resume” and “I am holding Web Bob pending your approval” now pass through the saved-state check. Useful answer text remains intact. Actual active holds produce the server's scoped hold reply; cleared holds produce no hold reminder. Ordinary explanations and paused-video text remain unchanged.

The new regressions failed before these fixes and passed afterward. No scheduler, worker executor or queue schema changed.

### Full-suite validation

Validation used a private snapshot of tracked base `c40e68a7dc0dc8e6f9347f6d3c22a70e2b546d54` plus this follow-up's intent, dispatch, reply, test and proof changes. Unrelated UI edits arriving in the shared checkout were excluded from this snapshot and this commit.

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **210 passed**, 12.549 s |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed**, 2.590 s |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `python3 bootstrap.py check` | **syntax: PASS** |
| `python3 -m py_compile` on changed Python files | **Passed** |
| `git diff --check` on this follow-up's files | **Passed** |

No tests were skipped. Service restart messages came from mocked watchdog tests. Four added regressions cover named confirmations, scoped resumes, missing/excluded project targets across reloads, and five paused/approval phrasings before and after `go`, including final reply delivery through Chat.

### Isolated HTTP proof

The expanded [proof runner](../webchat/isolated_intent_proof.py) used authenticated login, CSRF-protected `/api/messages`, `/api/jobs`, and a fresh private queue. The actual receipt for Jeff's priority-then-push exchange was:

```text
Web Bob: Queued for Codex — job webchat-d77da4f747ba56b296384c0000f26f8b.
WebJam: Queued for Cursor — job webchat-f4e7a83cb68e5e8091835e949d02b04f.
AdoptIQ: Queued for Codex — job webchat-2fee25dd62a551489f03e6b0e5a9339c.
StoryBoard: Queued for Cursor — job webchat-113a301739275f5db04cb75f51f42fc5.
```

A second inline four-project request used a busy-Codex/ready-Cursor lane fixture and assigned every project to the compatible available Cursor lane. A third saved project plan accepted the named “Go ahead with …” confirmation under the same fixture. Coding capability limits remain unchanged. A held login fix was blocked, then `resume` created exactly one job. A separate bare `go` cleared its saved hold without inventing work. Missing and fully excluded project requests preserved their active hold across reloads. Three deliberately stale provider fixtures each became “Ready when you are.”

10 private Chat reloads and 5 HTTP retransmissions preserved IDs without duplicate jobs. The final journal contained exactly **13 enqueue events**: four original projects, one resumed login fix, four inline projects, and four projects confirmed by the named go. Every row matched `/api/jobs`, remained `queued`, had zero attempts and no claimed worker. Lane availability and stale replies were fixtures; no external model or worker was launched, and this proof does not claim execution of the requested project work.

The proof ran **2026-09-27T19:53:28.148328+00:00 → 2026-09-27T19:53:28.858024+00:00**. Its [raw evidence](WEBBOB-CLEAN-0927.intent-recheck-evidence.json) records the exchanges, saved permissions, real queue rows, retries, source hashes and queue SHA-256 `ac96e3f36d825614078dcbe2604e983b2760e1df4e1968bb9a0f7bce3719b336`. Source hashes match the final implementation and proof files.

The live listener remained **PID 99149**, started **Sun Sep 27 12:40:03 2026**, and all seven service screen identities were unchanged. No live service restart, merge, force-push or Grok invocation occurred.

```sh
python3 webchat/isolated_intent_proof.py --output reviews/WEBBOB-CLEAN-0927.intent-recheck-evidence.json
```

## Follow-up 4: phone-first Jobs

PASS. Jobs now starts with **Working now**, with one card per observed job or lane screen: project, task, actual worker/model when reported, elapsed time and a live dot. **Recently finished** shows the last five terminal journal entries, with saved results and recorded PR links. A native, initially collapsed **Details** disclosure contains provider health, recorded API cost, waiting assignments and source ages. Cards use Chat's colors, rounded surfaces and spacing. Unreadable or damaged cost ledgers say “Not reported”; they never imply zero spend.

The new authenticated `/api/jobs/activity` endpoint reads `conductor/state/queue.jsonl`, the legacy job journals, current `screen -ls`/`ps` observations, `provider-health.json` and cost ledgers. Reads do not repair journals, acquire queue claims, refresh dashboards or launch workers. Queue claims, CLI wrappers and workers in the same lane produce one card. Open screens without a verified worker are labeled accordingly; stale claims stay in Details. Missing process or queue checks and failed requests show an unavailable message instead of an idle claim. The verified empty state is exactly **“Nothing running right now.”**

Jobs no longer renders NOW/handback text, dashboard rows, round scores, scheduler copy, self-improve bootstrap instructions, raw commits or placeholder SHAs. Known drill entries are excluded. Standalone CLI assignments can use their explicit “Follow-up …” task header as a label; the rest of the process prompt is omitted. Missing exact model variants are never guessed. Finished rows are ordered by completion time, so later delivery receipts do not reorder old work. Result buttons open saved text in the authenticated report dialog; local result paths must resolve inside the data root, and external links accept only HTTP(S) without embedded credentials.

### Validation

The shared checkout received concurrent tab edits during this task, so this follow-up was completed in a separate worktree. It was rebased onto the already-pushed chat-intent recheck `eb73d23`, preserving that work. The overlapping Jobs implementation in `fce7644` was retained, with an additional verification pass for queue-read failures, unknown costs and dashboard independence. The final combined branch passed:

| Command/check | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **227 passed**, 13.336 s |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed** |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `python3 bootstrap.py check` | **syntax: PASS** |
| `node --check webchat/static/app.js` and `git diff --check` | **Passed** |
| Headless Chromium at 320, 390, 430 and 900 CSS pixels, dark and light | **Passed; no horizontal overflow or page errors** |

Seventeen added Python regressions cover queue/process/screen deduplication, live lanes with an empty queue, explicit standalone task labels, stale drill/dashboard exclusion, honest paused/unavailable states, latest-five completion ordering, persisted health/cost, authenticated redacted results, missing files, unsafe URLs, path/symlink escapes, unreadable/torn queues and unknown cost records and plain service-task labels. No tests were skipped. Service-suite restart messages are from mocked watchdog tests.

### Phone screenshot and isolated browser proof

[Phone screenshot: webbob-jobs-0927.png](webbob-jobs-0927.png) — **390 × 844 CSS pixels**, device scale 2, dark theme. This is an actual read-only host observation served through a fresh private Chat instance on an ephemeral loopback port, not the live listener. At capture, 3 workers were active and five recent terminal jobs were available. Details remained collapsed. Both the main screenshot and the [scrolled recent-results screenshot](webbob-jobs-0927.finished.png) were visually reviewed after capture.

The [browser proof](../webchat/isolated_jobs_proof.py) also uses private journal/process fixtures to check two deduplicated cards, five finished rows, result opening, escaped result content, the recorded PR link, disclosure state across polling, the exact empty state, unavailable process checks and HTTP failure/recovery. It also verifies that an unreadable queue cannot show the idle state, and that Chat/Jobs never request the legacy dashboard endpoint. Normal conversation polling stays healthy during the proof; unexpected HTTP failures now fail it. The fixture's `test-model` values are test inputs only; the saved screenshot uses actual host observations. No external model or worker was started.

The final proof ran **2026-09-27T20:05:36.760896+00:00 → 2026-09-27T20:05:39.279304+00:00**. [Raw evidence](WEBBOB-CLEAN-0927.jobs-evidence.json) records the viewport checks, sanitized live data, zero provider calls and matching source/screenshot hashes. The private queue was unchanged. The live listener remained **PID 99149**, started **Sun Sep 27 12:40:03 2026**, and all seven service screen identities matched before and after. No live restart, deployment, merge, force-push or Grok invocation occurred.

```sh
# Use the existing Playwright runtime and Chromium; set BOB_PLAYWRIGHT_MODULE
# and BOB_CHROMIUM_PATH when they are outside the default module/cache paths.
python3 webchat/isolated_jobs_proof.py --live-root /path/to/bob-overnight-inject
```


## Follow-up 5: all five tabs, phone first

PASS. Chat, Jobs, Songs, Models and Settings now use the same spacing, readable text, touch targets and collapsed details. This follow-up builds on the finished Jobs redesign and source-error fixes (`fd2967a`), preserving grouped work cards, the five most recent results, safe result/PR links and the saved-result viewer.

| Tab | Cleanup and resulting behavior | Phone screenshot |
| --- | --- | --- |
| Chat | Removed unfinished attachments and canned round/council requests. View jobs opens current work without sending a message. One conversation picker, compact reply tools, collapsed/deduplicated retry details in plain words, and an honest empty conversation. Unsupported voice controls are hidden. | [Chat](webbob-tab-chat-0927.png) |
| Jobs | Current project/task/model/time remains first. Added Refresh, omitted unreported metadata, removed duplicated model/cost rows, and kept queue/check details collapsed. Failed or expired refreshes clear working and finished cards. A service name is not used as a task description. | [Jobs](webbob-tab-jobs-0927.png) |
| Songs | A real empty library leads to New song. Lyrics and Save come first; chords, notes, audio and saved versions are collapsed. Actual saved timestamps replace vague status text. New/switch clears prior audio and versions. Save failures retain edits and never claim they were saved. Audio's temporary association with the editor is stated plainly. | [Songs](webbob-tab-songs-0927.png), [empty editor](webbob-tab-songs-editor-0927.png) |
| Models | One card per model, showing current activity and reply availability. Removed dashboard, score, round and builder rows. Measured costs, plan use, retry times and dated last replies appear only when present, inside Details. Live workers override a cached ready label. | [Models](webbob-tab-models-0927.png) |
| Settings | Reply selection is first and persists on the device. All supported model choices say “first,” with fallback explained. Voice and actual scheduling status are collapsed. Removed repeated chats, old changelog, setup commands and internal loop/tick language. | [Settings](webbob-tab-settings-0927.png) |

Models and Settings read the authenticated, redacted, read-only `/api/overview`; Jobs keeps `/api/jobs/activity` and its existing result endpoint. These tab reads do not use or refresh the old dashboard or handback ledger. Usage comes directly from saved measurements: a missing, damaged or unknown ledger does not become $0, no budget ceiling is invented, and expired or day-old plan observations are omitted. Jobs and Models discard responses older than 30 seconds and clear old values when checks fail. Missing checks remain distinct from confirmed empty state. Open details survive polling.

### Validation

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **235 passed**, 14.436 s |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed**, 2.697 s |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `python3 bootstrap.py check` | **syntax: PASS** |
| JavaScript syntax and `git diff --check` | **Passed** |
| All-tab headless Chromium proof | **23 layout checks passed**: all five tabs at 320/390/430 px, all five in light mode at 390 px, and the song editor at all three phone widths |
| Existing Jobs browser proof after integration | **Passed**: grouped worker/queue evidence, five-result limit, safe result dialog/links, preserved disclosure state, empty/unavailable/unreadable-queue cases, no legacy-dashboard requests, 320/390/430/900 px in dark and light mode |

No tests were skipped. The service-suite restart lines are mocked watchdog output. New regressions cover authenticated/redacted read-only data, damaged queues, live claim/process deduplication, missing/stale/invalid usage, provider-status failure isolation, and service names not masquerading as task descriptions. Browser cases also exercise real private song saves and reloads, failed saves, unsaved-edit protection, cleared audio/history, persisted model preference, stale/error response removal, duplicate rows and plain retry details.

### Capture and isolation

The five requested PNGs are **390 × 844 CSS pixels at 2× scale**. The final images were visually reviewed. They come from an authenticated temporary data root and an ephemeral loopback listener, with actual empty private chat/song data and read-only host worker observations. Model status is the private instance's real unchecked state plus current worker activity; the captures do not claim successful model generation. The extra editor capture is a blank unsaved song. Fixture payloads and test-authored lyrics are used only in later regression cases, not in these screenshots.

[All-tab evidence](WEBBOB-CLEAN-0927.tabs-evidence.json) records the observed data, layout measurements, source/image SHA-256 hashes and before/after listener/service identities. [Jobs integration evidence](WEBBOB-CLEAN-0927.tabs-jobs-evidence.json) records the retained Jobs behavior; its extra screenshots are temporary proof files. One earlier concurrent capture failed its host-observation comparison even though the UI assertions passed. An immediate read and the final serial capture matched the original listener and seven services. The proof now retains both observations even when that comparison fails.

The final all-tab capture kept the live web listener at **PID 99149**, started **Sun Sep 27 12:40:03 2026**, and matched all seven service identities before and after. No live restart, deployment, merge, force-push, worker execution or external model call was performed by this follow-up. No Grok was invoked.

Reproduce with Playwright and a compatible cached Chromium (the two environment variables can be omitted when installed normally):

```sh
BOB_PLAYWRIGHT_MODULE=/path/to/playwright BOB_CHROMIUM_PATH=/path/to/chromium \
  python3 webchat/isolated_tabs_proof.py --output-dir reviews

BOB_PLAYWRIGHT_MODULE=/path/to/playwright BOB_CHROMIUM_PATH=/path/to/chromium \
  python3 webchat/isolated_jobs_proof.py --live-root .. \
  --screenshot /tmp/webbob-followup5-jobs-integration.png \
  --output reviews/WEBBOB-CLEAN-0927.tabs-jobs-evidence.json
```

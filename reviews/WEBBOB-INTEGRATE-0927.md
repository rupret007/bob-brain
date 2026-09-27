# Web Bob integration proof — 2026-09-27

Updated: `2026-09-27T16:32:30+00:00`. All receipt timestamps below are UTC; Chicago was UTC−05:00.

Branch: `draft/webbob-integrate-0927`. Tested and deployed code: `4198a1c76cf77cc218ae2fadac869173534b6516`. Endpoint: `http://127.0.0.1:8787`.

## Outcome

**5/5 forced providers have real lane/job citations; 4/5 real worker tasks have succeeded and delivered an answer in their originating chat.**

**Not a five-provider task PASS yet.** Cursor is queued behind an unrelated, suspended R39 council process. At 16:23 UTC, PID `92732` (`conductor/services/council.py`) owned `conductor/locks/lane-cursor.lock`; it and its Cursor child `94281` had process state `T` and had been alive for over 34 minutes. The exact suspension start is unknown; subsequent checks through 16:32 UTC still showed both stopped. They were not resumed, terminated, or restarted by this integration. Permission to resume the council was requested because it is outside the two authorized service restarts. No claim or completion is fabricated. Two read-only Cursor test requests remain durable: the earlier attempt `webchat-e283481ccbd750819e73e888bb585836` and the final-revision attempt `webchat-bed68a1563bf5201b528ea43259ebcae`. The polling harness was stopped; the service runner remains healthy and will claim these when the lane becomes available.

## Integration and repairs

- The branch already contained merge `5bafd5b` when this session began. Both dispatch `1f62705` and live-context `d5a8926` are ancestors of the tested revision. No merge conflict remains.
- `parse_do_more` is present in `webchat/job_queue.py` from dispatch commit `1f6c042`; the app and full webchat suite import it successfully.
- The shared snapshot reaches every provider and includes all three queue journals: `conductor/jobs.jsonl`, `conductor/queue.jsonl`, and `conductor/state/queue.jsonl`. It retains exact total counts, worker attribution, screen presence, service health, disk, and valid JSON under the prompt budget. Completed jobs stay historical; old drill text is excluded as current evidence.
- Explicit provider selection bypasses local canned status responses and never silently falls back to another provider.
- Existing follow-ups `9f2e9ee` and `857e1c8` keep tests independent of the live checkout and make metered API helpers import deployed code while loading credentials/data from the existing live root.
- Live status answers initially inferred idle/stale locks from empty queue claims. Commit `4198a1c` clarifies that background activity may hold a lane without a journaled job, requests full job IDs, and instructs models to identify unknown activity honestly.
- The live proof caught a race where the chat answer arrived after an older queue read. The harness now refreshes the terminal record and resumes an existing task/request without submitting a duplicate. `test_live_integration_proof.py` reproduces that race.

## Tests

| Check | Result |
|---|---|
| `python3 -m unittest discover -s services -p 'test_*.py'` | 82 passed, 2.194 s |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | 134 passed, 12.489 s |
| `node --test webchat/test_quiet_hours_js.mjs` | passed |
| `python3 bootstrap.py check` | syntax PASS |
| Separate `bash -n` invocation for each service launcher plus webchat run/start | 10 scripts passed |
| `plutil -lint launchd/*.plist` | 3 plists passed |
| `git diff --check` | passed |

All 216 Python tests pass. Unit-test failure-path logs (including mocked reviewer restarts and HTTP failures) are expected fixtures; they did not restart live services. JavaScript behavior is also exercised by the Python suite.

## Pinned deployment

- Code root: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-0927-service`; live data root: `/Users/jeffstory/Documents/bob-overnight-inject`.
- Both ignored runtime pins, `conductor/state/dispatch-code-root` and `conductor/state/webchat-code-root`, point to this checkout. The latter had independently pointed chat at the older e2e checkout and needed to be aligned.
- The deployment is an independent local clone with no remote. Its `last-good` tag points to the tested code. All 270 tracked files matched the tested source when activated.
- Final activation: `2026-09-27T16:25:13.321921+00:00` → `2026-09-27T16:25:15.434302+00:00`. Actual executable paths and authenticated API access were verified.
- Only `svc-webchat` and `svc-job-runner` were restarted. All other screen identities were unchanged across final activation. Existing conversations, credentials, queue, logs, and data roots were retained.
- During the earlier activation, closing screen sessions left the old children alive. The watchdog relaunched only job-runner; the verified old chat process was terminated before relaunch. Final activation stopped the two verified service PIDs before replacing their screens.

| Service | Before final activation | After final activation | Current PID |
|---|---|---|---|
| svc-webchat | `19784.svc-webchat` | `26096.svc-webchat` | 26100 |
| svc-job-runner | `19406.svc-job-runner` | `26092.svc-job-runner` | 26099 |

Runtime source SHA-256:

| File | SHA-256 |
|---|---|
| `webchat/providers.py` | `95129305582a16eefbd3a431d3a0d4a90917cae737156f40d7d59795d5cd6367` |
| `webchat/live_status_snapshot.py` | `514c783b49232b32484873bf22348e8d0ba24323e6c17ef79f6f9afa26054694` |
| `webchat/app.py` | `c4525af143051cbb30a5ad8be57df7e713ed8cd67c805426810ba38f8a8f69cf` |
| `webchat/api_call.py` | `e6a12d1ac2f12382108be20d94bdfdfac85af49630f5f2574b5c54eb1ac8fdda` |
| `services/web_dispatch.py` | `2348027497f5c10d52adfcec3b67f2a28ff9154a918e3efe949e067383cb28e6` |
| `services/dispatch_worker.py` | `193e2c4d84a5a9d1b0b13855c973a86b14aeae886c914108f9bd90f1a9d8ea59` |
| `state/task_queue.py` | `d0c82538dd6d82e12e04b9dc3a32be2003b6c24e0c36944b974d59eb2331219d` |

## Live method

The harness logs in locally, creates conversations, and sends authenticated `POST /api/messages` calls with `provider` forced to minimax, gemini, codex, claude, then cursor. Each starts with exactly `what are the workers doing right now`. A follow-up requests full job IDs and screen names if the first answer lacks one of those. Before/after snapshots validate cited IDs and screen names against real runtime state.

Small tasks use the same API with both `provider` and `worker` explicitly selected. MiniMax/Gemini/Claude analyze actual earlier dispatch timing evidence; Codex/Cursor read `webchat/live_status_snapshot.py` in their assigned local checkout and report line-specific findings. The proof checks durable claim/running/succeeded events, worker identity, exact result SHA-256, and one terminal answer in the originating conversation. No manual queue insertion, claim, completion, model stub, or chat-result insertion is used for live proof.

The timing task supplies historical timestamps from task `webchat-c96d2c7fba4452dc8ad2cbb5fc65e875`. Expected durations are 0.936 s queue-to-claim, 17.090 s execution, 0.093 s delivery, and 18.228 s end-to-end. Those numbers are the task input/output analysis; the separate table below records the new tasks’ actual execution.

Citations and lane timestamps are observations. Cached lane metadata and a lack of journaled claims cannot prove that every background process is idle; model interpretations do not override the raw receipts.

## Provider and task receipts

| Provider | Exact-question jobs / screens / lanes cited | Status follow-ups | Task state | Attempts |
|---|---|---|---|---|
| minimax | 1 / 4 / 5 | 0 | succeeded | 1 |
| gemini | 5 / 0 / 5 | 1 | succeeded | 1 |
| codex | 3 / 8 / 5 | 0 | succeeded | 1 |
| claude | 4 / 0 / 5 | 1 | succeeded | 1 |
| cursor | 5 / 9 / 5 | 0 | queued | 0 |

| Provider | Task | Queued UTC | Claimed UTC | Finished UTC | Answer saved UTC |
|---|---|---|---|---|---|
| minimax | `webchat-d9ecfa6b35dd5b6fa9962614fa25439b` | 16:25:40.295 | 16:25:43.196 | 16:26:00.625 | 16:26:00.640 |
| gemini | `webchat-3f11455eab4c5f5586f63200b3398377` | 16:26:11.203 | 16:26:16.352 | 16:26:17.747 | 16:26:18.171 |
| codex | `webchat-1be99aaf94f3595ab1cffb5638a7e5b1` | 16:26:33.799 | 16:26:36.778 | 16:26:55.298 | 16:26:55.564 |
| claude | `webchat-1829b9b6c6ee58c2bd81e3282fae162f` | 16:28:30.032 | 16:28:33.597 | 16:28:49.579 | 16:28:50.359 |
| cursor | `webchat-bed68a1563bf5201b528ea43259ebcae` | 16:29:02.649 | pending | pending | pending |

### minimax

Conversation: `2feeaf5b-56ca-4cf0-bcfe-f613f1510df7`.

Status turn 1: `dd8801fa-b86f-490e-81c3-bec99f77e6e0`; submitted `2026-09-27T16:25:27.869+00:00`; completed `2026-09-27T16:25:40.276+00:00`; actual provider `minimax`.

Question: what are the workers doing right now

Actual chat answer:

```text
**Workers right now (live snapshot 16:25 UTC):**

**Services — all 4 healthy:** job-runner (4.6s ago), reviewer (86s), dashboard-updater (131s), watchdog (101s). Plus svc-disk-watch, svc-webbob-reviewers, svc-webchat, svc-webchat-ready-r39.

**Lanes:** cursor=busy (lease held, no journaled job), claude/codex/gemini/minimax=ready.

**Queue:** 1 job queued — `webchat-e283481ccbd750819e73e888bb585836` (cursor). Zero claimed. 124 done, 14 failed history.

**Disk:** 13.5 GB free (84% used) — caution.

No active coding workers. Lane busy lock is held but cursor has no claimed job right now.
```

Matched job IDs: `webchat-e283481ccbd750819e73e888bb585836`.

Task request: `3d264c20-c90e-491c-a9e3-c82b45150830`; task `webchat-d9ecfa6b35dd5b6fa9962614fa25439b`.

Review this actual Web Bob dispatch timing measurement from task webchat-c96d2c7fba4452dc8ad2cbb5fc65e875 on 2026-09-27 UTC: queued 15:26:31.279, claimed 15:26:32.215, execution started 15:26:32.324, finished 15:26:49.414, chat answer saved 15:26:49.507. Calculate queue wait, execution time, delivery delay, and end-to-end time in seconds to three decimals. Identify which stage dominates. Return a compact table and one conclusion under 140 words.

Result message: `0abb5b53-328f-5dda-afcf-81356075f165`; result SHA-256: `4679b7f85b1f7f7b6d9a9f7ce11f71a84e199ffef0b04574c7c465e7092627f5`.

Actual task answer in chat:

```text
minimax finished:

| Metric | Seconds (s) |
|--------|-------------|
| Queue Wait | 0.936 |
| Execution Time | 17.090 |
| Delivery Delay | 0.093 |
| End‑to‑End | 18.228 |

**Conclusion** – Execution dominates, taking 17.090 s (~94 % of the 18.228 s end‑to‑end latency). Queue wait (0.936 s) and delivery delay (0.093 s) are negligible. Optimizing the execution phase will yield the greatest reduction in overall response time.
```

Journal events: enqueued (16:25:40.295) → claimed (16:25:43.196) → running (16:25:43.270) → heartbeat (16:25:53.282) → succeeded (16:26:00.625) → delivered (16:26:00.642).

### gemini

Conversation: `72968bd7-f274-4f2a-90e8-4abedd0c636e`.

Status turn 1: `50b23f2e-a393-4472-9bb2-d430148992f5`; submitted `2026-09-27T16:26:00.672+00:00`; completed `2026-09-27T16:26:04.895+00:00`; actual provider `gemini`.

Question: what are the workers doing right now

Actual chat answer:

```text
Right now, all 4 services are healthy.

Here's what's happening on the lanes:
*   **Cursor** and **MiniMax** are currently busy.
*   **Codex**, **Claude**, and **Gemini** are ready for new tasks.

There's 1 job currently queued: `webchat-e283481ccbd750819e73e888bb585836` for the Cursor worker.

Here are some recent jobs that have completed:
*   `webchat-d9ecfa6b35dd5b6fa9962614fa25439b` (MiniMax) - Succeeded
*   `webchat-7320095f6586511b8e5e1ff9d2da0ccc` (Claude) - Succeeded
*   `webchat-acf2569cf92a5267b0af95dc5a5b8d60` (Codex) - Succeeded
*   `webchat-0c160c28931a54db82f1d225ede276d7` (Gemini) - Succeeded

Disk usage is at 84% with 13.48 GB free.
```

Matched job IDs: `webchat-0c160c28931a54db82f1d225ede276d7`, `webchat-7320095f6586511b8e5e1ff9d2da0ccc`, `webchat-acf2569cf92a5267b0af95dc5a5b8d60`, `webchat-d9ecfa6b35dd5b6fa9962614fa25439b`, `webchat-e283481ccbd750819e73e888bb585836`.

Status turn 2: `225308ac-1b5d-4f3e-a7f0-184166b4cda2`; submitted `2026-09-27T16:26:04.915+00:00`; completed `2026-09-27T16:26:11.177+00:00`; actual provider `gemini`.

Question: Which specific worker lanes, screen names, and full job IDs support that status? Use the current live_status_snapshot. If nothing is claimed, label recent finished jobs as history.

Actual chat answer:

```text
Okay, here's a more detailed breakdown of what's happening right now, including screen names and job IDs from the `live_status_snapshot` at 2026-09-27T16:26:05+00:00:

**Services (all healthy):**
*   `svc-dashboard-updater` (PID session: `17509.svc-dashboard-updater`)
*   `svc-disk-watch` (PID session: `94801.svc-disk-watch`)
*   `svc-job-runner` (PID session: `26092.svc-job-runner`)
*   `svc-reviewer` (PID session: `45974.svc-reviewer`)
*   `svc-watchdog` (PID session: `53542.svc-watchdog`)
*   `svc-webbob-reviewers` (PID session: `77277.svc-webbob-reviewers`)
*   `svc-webchat` (PID session: `26096.svc-webchat`)
*   `svc-webchat-ready-r39` (PID session: `80604.svc-webchat-ready-r39`)

**Worker Lanes & Jobs:**

*   **Cursor Lane:**
    *   **State:** Busy (lane lease held)
    *   **Active Job:** The `active_jobs` list for Cursor is currently empty, but the lane lease is held, indicating background work.
    *   **Queued Job:** `webchat-e283481ccbd750819e73e888bb585836` is queued for the Cursor worker.
    *   **Log Tail:**
        ```
        - `python3.11 -m unittest tests.test_bridge_port_conflict -q` — OK (9 tests)
        ## Remaining risks
        - CI not run in this worktree session; full matrix unverified here.
        ```

*   **Codex Lane:**
    *   **State:** Ready (available)
    *   **Log Tail:**
        ```
        - Local test prerequisite check: /usr/bin/python3 lacks PySide6; no local pytest run performed. Test results above are verified GitHub CI results.
        - No source/test changes, commit, or push made. No changes to other checkouts or orchestrator files. This note is the only local change.
        - BLOCKER: assigned failing test is already green at the current PR head; the current red failures are outside the specified test fix.
        ```

*   **Claude Lane:**
    *   **State:** Ready (available)
    *   **Log Tail:**
        ```
        - No failures to reproduce; no code changes made; nothing pushed.
        - Local unittest run: 10 tests pass; test_parametric_design and test_shelf_mini fail to import only
        because numpy is not installed in this local Python (environment gap, not a repo defect; CI installs requirements.txt).
        ```

*   **Gemini Lane:**
    *   **State:** Ready (available)

*   **MiniMax Lane:**
    *   **State:** Ready (available)

**Other Screen Sessions (no job journal match):**
*   `lane-webbob-integrate` (PID session: `14865.lane-webbob-integrate`) - Its current task is unknown from this snapshot.

**Job History (recently completed):**
*   `webchat-d9ecfa6b35dd5b6fa9962614fa25439b` (MiniMax) - Succeeded
*   `webjam-ci-handoff-1937` - Harvested
*   `webchat-7320095f6586511b8e5e1ff9d2da0ccc` (Claude) - Succeeded
*   `webjam-ci-help-1738` - Harvested
*   `webchat-acf2569cf92a5267b0af95dc5a5b8d60` (Codex) - Succeeded
*   `webchat-0c160c28931a54db82f1d225ede276d7` (Gemini) - Succeeded
*   `webchat-73b6b4eb83bf5b9e990a8ca24641b72f` (MiniMax) - Succeeded

**Disk Status:**
*   13.48 GB free on `/System/Volumes/Data` (84% used).
```

Matched job IDs: `webchat-0c160c28931a54db82f1d225ede276d7`, `webchat-7320095f6586511b8e5e1ff9d2da0ccc`, `webchat-73b6b4eb83bf5b9e990a8ca24641b72f`, `webchat-acf2569cf92a5267b0af95dc5a5b8d60`, `webchat-d9ecfa6b35dd5b6fa9962614fa25439b`, `webchat-e283481ccbd750819e73e888bb585836`, `webjam-ci-handoff-1937`, `webjam-ci-help-1738`.

Task request: `904f8076-dc36-430a-a135-607f7fd7f99f`; task `webchat-3f11455eab4c5f5586f63200b3398377`.

Review this actual Web Bob dispatch timing measurement from task webchat-c96d2c7fba4452dc8ad2cbb5fc65e875 on 2026-09-27 UTC: queued 15:26:31.279, claimed 15:26:32.215, execution started 15:26:32.324, finished 15:26:49.414, chat answer saved 15:26:49.507. Calculate queue wait, execution time, delivery delay, and end-to-end time in seconds to three decimals. Identify which stage dominates. Return a compact table and one conclusion under 140 words.

Result message: `d8e2a772-b0d6-5214-b940-15a865a332db`; result SHA-256: `bfb5fdc2d8417c9e14fff559d1edd10c50421839123884131e099ec7b055b28d`.

Actual task answer in chat:

```text
gemini finished:

Here's the analysis of the Web Bob dispatch timing:

| Metric            | Time (seconds) |
| :---------------- | :------------- |
| Queue Wait        | 0.936          |
| Execution Time    | 17.090         |
| Delivery Delay    | 0.093          |
| End-to-End Time   | 18.228         |

**Conclusion:**
Execution time is the dominant stage, accounting for approximately 93.7% of the total end-to-end time. The queue wait and delivery delay are relatively minor contributors to the overall task duration. Optimizing the execution phase would yield the most significant improvements in dispatch timing.
```

Journal events: enqueued (16:26:11.203) → claimed (16:26:16.352) → running (16:26:16.440) → succeeded (16:26:17.747) → delivered (16:26:18.174).

### codex

Conversation: `0248ff98-6b6e-4077-94a8-ed4b3540d830`.

Status turn 1: `399c9aa3-8562-40b8-b03d-0258f36a1e82`; submitted `2026-09-27T16:26:19.394+00:00`; completed `2026-09-27T16:26:33.773+00:00`; actual provider `codex`.

Question: what are the workers doing right now

Actual chat answer:

```text
Jeff, the **11:26:19 AM CT snapshot** shows services healthy, but doesn’t establish that every worker is doing project work.

- **Cursor:** busy lease at **11:26:16 CT**, current task unknown; no journaled claim. Cursor job `webchat-e283481ccbd750819e73e888bb585836` is **queued**, not running.
- **Codex, Claude, Gemini, MiniMax:** lanes marked ready at **11:26:15–16 CT**. **History:** Gemini job `webchat-3f11455eab4c5f5586f63200b3398377` succeeded; the runner logged its claim at 11:26:16.
- **Other screens present:** `lane-webbob-integrate`, `svc-webchat-ready-r39`, and `svc-webbob-reviewers`. Their specific current tasks aren’t identified.
- **Services:** `svc-job-runner`, `svc-reviewer`, `svc-dashboard-updater`, and `svc-watchdog` are **4/4 healthy**. Reviewer’s latest log reports a review of `webjam-ci-handoff-1937`: Claude/MiniMax/Gemini true, Cursor false.
- **Disk:** **13.46 GB free**, 84% used.

There are **zero claimed queue jobs**—that doesn’t mean the background workers are idle.
```

Matched job IDs: `webchat-3f11455eab4c5f5586f63200b3398377`, `webchat-e283481ccbd750819e73e888bb585836`, `webjam-ci-handoff-1937`.

Task request: `2a6b0a0f-62ae-46b7-a1f4-ba5dbe841d1d`; task `webchat-1be99aaf94f3595ab1cffb5638a7e5b1`.

Review webchat/live_status_snapshot.py in your assigned checkout. Read the file and report the three queue journal paths it reads, how succeeded tasks and harvested result jobs are classified, and how prompt encoding avoids cutting JSON. Cite at least two line numbers. Do not modify files. Return a concrete review under 180 words.

Result message: `3efeda22-61d2-579a-8ba6-a8a5f1c33952`; result SHA-256: `c96461eb610aaf584001e5ff619553644210c9ff1a7f007cbdb38d454eb6b374`.

Actual task answer in chat:

```text
codex finished:

- **Queue journals:** `_latest_jobs()` reads `conductor/jobs.jsonl`, `conductor/queue.jsonl`, and `conductor/state/queue.jsonl`, relative to the supplied root ([line 71](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webchat-1be99aaf94f3595ab1cffb5638a7e5b1/webchat/live_status_snapshot.py:71)).
- **Classification:** `succeeded` maps to `done`. `harvested` maps to `failed` when its outcome is `blocked`; otherwise it maps to `done`. The succeeded check takes precedence even over a blocked outcome ([lines 87–94](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webchat-1be99aaf94f3595ab1cffb5638a7e5b1/webchat/live_status_snapshot.py:87)).
- **JSON-safe encoding:** `encode_snapshot()` copies the snapshot and repeatedly serializes complete, compact JSON. If oversized, it removes whole list entries in this order: failed history, done history, logs, queued jobs, claimed jobs, screen lanes. It preserves totals and required fields, marks `lists_trimmed`, and raises `ValueError` if required fields cannot fit. It never slices serialized JSON ([lines 347–364](/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webchat-1be99aaf94f3595ab1cffb5638a7e5b1/webchat/live_status_snapshot.py:347)).

No files modified.
```

Journal events: enqueued (16:26:33.799) → claimed (16:26:36.778) → running (16:26:36.851) → heartbeat (16:26:46.863) → succeeded (16:26:55.298) → delivered (16:26:55.566).

### claude

Conversation: `d6f904d9-287e-40ad-b9cf-4fa1d8c85545`.

Status turn 1: `8caf3234-fab2-4c50-aea7-5f275da5e763`; submitted `2026-09-27T16:26:56.229+00:00`; completed `2026-09-27T16:28:07.415+00:00`; actual provider `claude`.

Question: what are the workers doing right now

Actual chat answer:

```text
No file tools are available in this session, and this isn't actually a code-change task — it's a status question I can answer directly from the snapshot already in context. Here's the answer as Bob:

Right now: **codex** and **cursor** show their lane locks as busy, but nothing is claimed in the job journal — codex's last real work was the #159/#160 CI-fix verify (found the choice-helper test already green at PR head, no fix pushed, blocker `codex-webjam-ci-fix-choice-helper-2133` still open); cursor has one job queued (`webchat-e283481ccbd750819e73e888bb585836`). **claude, gemini, minimax** are all idle/ready — last thing they did was the 15:26:41Z council assessment pass and (claude) the shelf PR #10 CI check.

Services are 4/4 healthy. Queue: 0 claimed, 1 queued, 127 done, but **14 jobs are stuck failed/blocked** (mostly "legacy BLOCKER retained; explicit retry or escalation required" — webjam-identity-line-2238, cursor-queue-21/23, cursor-webjam-chip-2003, that same choice-helper job). Disk is down to 13.44 GB free (84% used).

Critique: the busy-but-unclaimed codex/cursor locks mean I genuinely can't tell you what's in them right now — that's a real visibility gap, not idleness. And you've asked this exact question ~6 times in the last 10 minutes across different providers; one answer should cover it going forward.
```

Matched job IDs: `codex-webjam-ci-fix-choice-helper-2133`, `cursor-webjam-chip-2003`, `webchat-e283481ccbd750819e73e888bb585836`, `webjam-identity-line-2238`.

Status turn 2: `399e60e6-f3e8-4877-9eb5-87b31786400f`; submitted `2026-09-27T16:28:07.439+00:00`; completed `2026-09-27T16:28:29.997+00:00`; actual provider `claude`.

Question: Which specific worker lanes, screen names, and full job IDs support that status? Use the current live_status_snapshot. If nothing is claimed, label recent finished jobs as history.

Actual chat answer:

```text
**Claimed:** nothing — `queue_jobs.claimed` is empty and `active_jobs` is empty for every lane (`codex`, `claude`, `gemini`, `minimax` all `ready`; `cursor` `busy` but with 0 active_jobs).

**Cursor's busy lock, unattributed:** `lane_locks.cursor` = `busy, "lane lease held"` with no active_jobs entry — I can't name a job or screen behind it from this snapshot; call it unknown, not stale. Its log tail is from finished work: `cursor-queue-22-...` (harvested/DONE) and a note "CI not run in this worktree session."

**Queued (1):** `webchat-e283481ccbd750819e73e888bb585836` — worker `cursor`, state `queued`.

**Screens running (9), all services or one stray lane:**
`svc-job-runner`, `svc-reviewer`, `svc-dashboard-updater`, `svc-watchdog`, `svc-webchat`, `svc-webchat-ready-r39`, `svc-disk-watch`, `svc-webbob-reviewers`, plus `lane-webbob-integrate` (role: other, "no job journal match" — unidentified task).

**History (recent done, not active):** `webjam-ci-handoff-1937` (codex, harvested), `webjam-host-checklist-mustfix-2058`, `webjam-join-empty-edges-2020`, `webjam-music-chips-1938`, `cursor-queue-19-webjam-novice-name-field-slice-6ea925c0`.

**Failed/blocked (14 total), full IDs:** `webchat-260071f0845f59359813ff1df7f5e351` (codex), `cursor-queue-23-recording-receipt-export-c42295f9`, `cursor-queue-21-webjam-novice-jamulus-handoff-copy-70f842ee`, `gemini-webjam-ux-evidence-b795c365`, `webjam-identity-line-2238`, `webjam-unique-value-round2-2112`, `webjam-rehearsal-recap-2112`, `webjam-recording-receipt-research-2131`, `webjam-novice-first-run-audit-2043`, `webjam-ci-handoff-b11a7c4-2111`, `cursor-webjam-unique-2114`, `cursor-webjam-novice-2114`, `cursor-webjam-chip-2003`, `codex-webjam-ci-fix-choice-helper-2133`.

**Critique:** most of that "failed" list is the same generic `"legacy BLOCKER retained; explicit retry or escalation required"` stamped on 8 different job_ids at the identical timestamp (1790482778.9x) — that's one bulk sweep event, not 8 independent failures, and it's telling you nothing job-specific. The real actionable one is `codex-webjam-ci-fix-choice-helper-2133`, which has an actual note (test already green at PR head). Also worth flagging: `cursor` shows `busy` but zero evidence of what — that gap is the honest answer, not something to paper over with the finished-job log tail sitting next to it.
```

Matched job IDs: `codex-webjam-ci-fix-choice-helper-2133`, `cursor-queue-19-webjam-novice-name-field-slice-6ea925c0`, `cursor-queue-21-webjam-novice-jamulus-handoff-copy-70f842ee`, `cursor-queue-23-recording-receipt-export-c42295f9`, `cursor-webjam-chip-2003`, `cursor-webjam-novice-2114`, `cursor-webjam-unique-2114`, `gemini-webjam-ux-evidence-b795c365`, `webchat-260071f0845f59359813ff1df7f5e351`, `webchat-e283481ccbd750819e73e888bb585836`, `webjam-ci-handoff-1937`, `webjam-ci-handoff-b11a7c4-2111`, `webjam-host-checklist-mustfix-2058`, `webjam-identity-line-2238`, `webjam-join-empty-edges-2020`, `webjam-music-chips-1938`, `webjam-novice-first-run-audit-2043`, `webjam-recording-receipt-research-2131`, `webjam-rehearsal-recap-2112`, `webjam-unique-value-round2-2112`.

Task request: `a1d0ae74-4279-43b5-8257-5e6a32acb092`; task `webchat-1829b9b6c6ee58c2bd81e3282fae162f`.

Review this actual Web Bob dispatch timing measurement from task webchat-c96d2c7fba4452dc8ad2cbb5fc65e875 on 2026-09-27 UTC: queued 15:26:31.279, claimed 15:26:32.215, execution started 15:26:32.324, finished 15:26:49.414, chat answer saved 15:26:49.507. Calculate queue wait, execution time, delivery delay, and end-to-end time in seconds to three decimals. Identify which stage dominates. Return a compact table and one conclusion under 140 words.

Result message: `b77d4b22-ac47-540e-bcb1-21acbe502492`; result SHA-256: `2c6dec0fee86dd0a5c453182b07de3c6416c5ca1ef8e4a58dd8c4f88dc5daec0`.

Actual task answer in chat:

```text
claude finished:

| Stage | Interval | Duration (s) |
|---|---|---|
| Queue wait | queued → claimed | 0.936 |
| Execution time | exec start → finished | 17.090 |
| Delivery delay | finished → answer saved | 0.093 |
| End-to-end | queued → answer saved | 18.228 |

(Claim-to-start dispatch overhead, not requested but incidental: 0.109s)

**Conclusion:** Execution time (17.090s) dominates, accounting for ~93.7% of the 18.228s end-to-end latency. Queue wait (0.936s, ~5.1%) and delivery delay (0.093s, ~0.5%) are minor by comparison. The bottleneck is model/task processing itself, not queuing or the save-back path — optimization effort should target execution, not dispatch infrastructure.
```

Journal events: enqueued (16:28:30.032) → claimed (16:28:33.597) → running (16:28:33.733) → heartbeat (16:28:43.745) → succeeded (16:28:49.579) → delivered (16:28:50.361).

### cursor

Conversation: `1c34bcbe-0129-4c0f-a097-c8ecb88790e4`.

Status turn 1: `3394ef49-2af0-4a36-851f-2ce6ce998152`; submitted `2026-09-27T16:28:50.429+00:00`; completed `2026-09-27T16:29:02.636+00:00`; actual provider `cursor`.

Question: what are the workers doing right now

Actual chat answer:

```text
Hey Jeff — snapshot as of **2026-09-27 16:28:50 UTC** (lane locks cached at that time).

**Conductor services:** all four core schedulers are healthy (`svc-job-runner`, `svc-reviewer`, `svc-dashboard-updater`, `svc-watchdog`). Job-runner tick was good a few seconds before that stamp. Reviewer last finished a pass on `webjam-ci-handoff-1937` (~5 min earlier). **Disk:** ~**13.4 GB** free on Data (**84%** full) — still in warn territory.

**Web Bob job queue:** **nothing claimed** right now. One job **queued** for Cursor: **`webchat-e283481ccbd750819e73e888bb585836`**. Recent **history** (not active): e.g. **`webchat-1829b9b6c6ee58c2bd81e3282fae162f`** (Claude), **`cursor-queue-22-webjam-novice-busy-session-remedy-f9df52cf`** harvested — Cursor note cites **`3eb3925`** on the busy-session remedy branch.

**Lane locks (no journaled claim ≠ idle):** **Claude** and **Cursor** = **busy** (lease held, `active_jobs` empty). **Codex, Gemini, MiniMax** = **ready**. Claude’s tail is shelf PR #10 green @ **`41c0dea`**; Cursor’s tail is queue-22 Jamulus port-in-use work + local pytest pass, CI not re-run in that session.

**Screens up (9):** the `svc-*` services above plus **`svc-webchat`**, **`svc-webchat-ready-r39`**, **`svc-webbob-reviewers`**, **`svc-disk-watch`**, and **`lane-webbob-integrate`** (no queue match — **current task unknown** from this snapshot).

**`next-prompts` INDEX** still lists rows **21** / **23** as RUNNING but **STATUS** has them **blocked** (uncommitted changes on 21, timeout on 23); **20** CI-fix and **17** identity line are **READY** waiting on the tick. **JEFF** lines: legacy blockers on **codex-webjam-ci-fix-choice-helper-2133** and **cursor-webjam-chip-2003** need explicit retry/escalation.

**BOB-STATE** is stale (00:27 CT) — it still mentions old `svc-webchat-ready` screens; trust this snapshot over that for “right now.”

If you want the scheduler to poke **row 20** (CI commit/push) or clear a blocker, say **`start a job: …`** or use the Jobs chip — I won’t claim anything ran until the server action card says so.
```

Matched job IDs: `codex-webjam-ci-fix-choice-helper-2133`, `cursor-webjam-chip-2003`, `webchat-1829b9b6c6ee58c2bd81e3282fae162f`, `webchat-e283481ccbd750819e73e888bb585836`, `webjam-ci-handoff-1937`.

Task request: `3444d0d7-1485-4a68-8419-2aa5ffdbf812`; task `webchat-bed68a1563bf5201b528ea43259ebcae`.

Review webchat/live_status_snapshot.py in your assigned checkout. Read the file and report the three queue journal paths it reads, how succeeded tasks and harvested result jobs are classified, and how prompt encoding avoids cutting JSON. Cite at least two line numbers. Do not modify files. Return a concrete review under 180 words.

Result message: `pending`; result SHA-256: `pending`.

Actual task answer in chat:

```text
(pending; no terminal answer claimed)
```


## Persistence and private evidence

- `2026-09-27T16:31:01.361+00:00`: all 7 saved status answers and the 4 completed task answers present exactly once; Cursor has no terminal answer (4 providers).

Private runtime receipts remain outside Git:

- `conductor/state/webbob-integration-proof-0927.json` — prompts, status snapshots, task events, answers, and hashes.
- `conductor/state/webbob-integration-deployment-0927.json` — deployment chain, code/data pins, process identities, and source hashes.
- `conductor/state/webbob-integration-proof-0927-before-status-fix.json` — earlier attempt, including the recovered proof-reader race and the first queued Cursor task.
- `conductor/state/queue.jsonl`, `conductor/state/task-runs/<task-id>/RESULT.md`, model/meter journals, and saved chat conversations.

Reproduce using `python3 webchat/live_integration_proof.py run --root /Users/jeffstory/Documents/bob-overnight-inject`; `resume` continues existing task receipts and skips completed providers; `verify` reopens saved chat answers and checks that they remain present exactly once.

Credentials, cookies, CSRF tokens, session secrets, and raw runtime files were not staged. Only local draft commits and a local deployment-clone fast-forward were made. No push, force-push, main merge, PR action, external message, or Grok call was performed.

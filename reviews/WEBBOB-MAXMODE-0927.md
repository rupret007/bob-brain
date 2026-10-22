# Web Bob max mode — final proof, 2026-09-27

**PASS.** After the chat hotfix was proved on three workers and recorded in [WEBBOB-HOTFIX-0927.md](WEBBOB-HOTFIX-0927.md), one authenticated max-mode request ran Codex, Cursor, Claude, Gemini and MiniMax concurrently, plus the local mini test worker. All six completed on their first attempt and produced one durable combined chat answer.

Final service code: `570bc5af223f87c1b149caa7bf9d8d3cb3b75359`. Five-model overlap: **4.672s**, from `2026-09-27T17:42:50.468+00:00` to `2026-09-27T17:42:55.140+00:00`. `/api/jobs` directly observed all five executing at `2026-09-27T17:42:51.190+00:00`. These are real model calls, not mocks or injected delays.

## Ranked gaps addressed

| Gap from WEBBOB-MAX-GAPS-0927.md | Final behavior |
|---|---|
| One request could not fan out | Saved plan expands a goal into distinct packages with immutable group ID, size and unique indices. Explicit worker packages or the default role split run through the durable queue. Partial appends recover before any member can claim. |
| Claude lacked chat failover | An explicit choice tries that provider first, then the normal fallback chain. Automatic ordinary chat still excludes Claude. Background retries prefer an untried compatible provider and wait if that alternative is busy. |
| API lanes serialized unnecessarily | Gemini and MiniMax each have three process-safe slots; CLI workers and mini each have one. Health metadata can lower capacity but cannot increase the configured ceiling. |
| Missing usage tiers and Gemini cap | Both APIs have a $48 maximum shared ceiling, configurable downward. Outstanding reservations count: warn at 70%, one API slot at 85%, reject a worst-case reservation crossing 95%. CLI percentages stay unknown without observed quota data; observed stops and rate-limit cooldowns are honored. |
| Fixed routing order ignored task fit | Coding uses Codex/Cursor, analysis prefers Claude and API lanes, local test work uses mini; caps and prior failures shift work to compatible resources with headroom. |
| Mini CPU was absent | Mini runs named local test suites with an isolated data root and stripped credentials, then uses the same durable result outbox. |

One local reducer posts the combined answer only after all members terminate, retaining worker attribution, disagreement and failures. It saves chat before acknowledging delivery; deterministic message IDs prevent duplicate answers. This is an attributed combined result, not an additional model vote or an automatic integration of coding branches. Code packages retain their local draft commits for review.

## Repairs found during the live review

- A failed provider could consume retries while untried alternatives were busy. The router now defers that retry without spending an attempt.
- Group validation previously counted rows without checking unique indices or immutable metadata. Enqueue, claim and reduction now validate membership; inconsistent replay is rejected.
- A health capacity override could raise a lane ceiling. Claims now clamp it to the configured maximum.
- A real Claude answer began `BLOCKER: none — completed`. The old parser treated it as failure and successfully retried the task on Gemini. The final parser accepts explicit no-blocker markers and still rejects genuine Markdown BLOCKER headings. The final live group completed all original workers without retries.
- Added explicit group chat-save failure coverage: no member is acknowledged until the combined answer is saved, and recovery emits it once.

## Final validation

- Services: **98 tests passed** (`python3 -m unittest discover -s services -p 'test_*.py'`).
- Webchat: **148 tests passed** (`python3 -m unittest discover -s webchat -p 'test_*.py'`).
- Total: **246 Python tests**. JavaScript quiet-hours test, `bootstrap.py check`, shell syntax checks and `git diff --check` also passed.
- Coverage includes real lock contention, concurrent claim/reservation races, every provider’s retry path, 70/85/95% tiers, coding capability restrictions, interrupted group creation, stale claims, grouped result recovery and rejecting fabricated overlap/duplicate proof answers.
- Unit-test log lines about service restarts and transport errors are isolated mocks; they are not live restarts or provider outages.

## Final deployment

Activated `2026-09-27T17:40:03.891084+00:00` from `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-0927-service`. Both code-root pins point to that checkout; the live data root is unchanged.
Only `svc-webchat` and `svc-job-runner` were restarted, after green tests. The deployment receipt verifies unchanged identities for all other screens. Runtime executable paths were checked against the requested integrate checkout.

| Service | Before | After |
|---|---|
| svc-webchat | `93015.svc-webchat` | `99147.svc-webchat` |
| svc-job-runner | `92947.svc-job-runner` | `99081.svc-job-runner` |

## Authenticated live receipts

Conversation: `9f7c4aaf-c44d-446b-9dde-543072fa29eb`. Request: `4176f630-e086-4412-ac9c-6ecc2945bbe3`. Group: `max-51c83ea4c72a56ccb852adf998e17fe6`. Submitted `2026-09-27T17:42:37.905+00:00`.
One `POST /api/messages` created all six packages. The harness observed `/api/jobs`, fetched the originating conversation, verified all terminal results and delivery acknowledgements, and checked one combined message. The password and cookies stayed in memory; nothing manually claimed, completed or inserted a result.

| Worker | Job ID | Claimed UTC | Executing UTC | Finished UTC | Delivered UTC |
|---|---|---|---|---|---|
| codex | `webchat-d10d5b84855a595ebae482626ddd0dec` | 2026-09-27T17:42:43.297+00:00 | 2026-09-27T17:42:43.683+00:00 | 2026-09-27T17:44:06.848+00:00 | 2026-09-27T17:44:07.197+00:00 |
| cursor | `webchat-05531cdfa27d5d4c80a29098142c2730` | 2026-09-27T17:42:50.237+00:00 | 2026-09-27T17:42:50.468+00:00 | 2026-09-27T17:43:11.726+00:00 | 2026-09-27T17:44:07.207+00:00 |
| claude | `webchat-f22d01ba515e5a48bdb1bbad9eaa1159` | 2026-09-27T17:42:43.313+00:00 | 2026-09-27T17:42:43.893+00:00 | 2026-09-27T17:43:19.044+00:00 | 2026-09-27T17:44:07.218+00:00 |
| gemini | `webchat-3db39c7d7e245657a842fb022a4a8be3` | 2026-09-27T17:42:43.340+00:00 | 2026-09-27T17:42:44.095+00:00 | 2026-09-27T17:42:55.140+00:00 | 2026-09-27T17:44:07.228+00:00 |
| minimax | `webchat-6807ef86e3fd56989f8f57cf9cd6da5f` | 2026-09-27T17:42:43.360+00:00 | 2026-09-27T17:42:44.296+00:00 | 2026-09-27T17:43:15.036+00:00 | 2026-09-27T17:44:07.239+00:00 |
| mini | `webchat-5bd5f7f4aceb50aa98743073998fb187` | 2026-09-27T17:42:43.377+00:00 | 2026-09-27T17:42:43.507+00:00 | 2026-09-27T17:42:46.154+00:00 | 2026-09-27T17:44:07.249+00:00 |

Combined message: `9c0aad1a-d7f2-521d-8ba1-a8a33e213469`, saved `2026-09-27T17:44:07.184+00:00`; status `succeeded`.
Answer SHA-256: `593a6a40c29bb76799723676cf19655981ef98a1035c71733b2494b3cdcde0af`. Its first line is **“Max mode completed: 6/6 subtasks succeeded.”** Each of the six worker sections is present; mini’s actual test output reports 43 passing service tests.

### Idle refill

While other group members were still running, a separate Gemini task `webchat-2325f8a303335d3791693094aef3efd1` was submitted through chat in conversation `6d4876d8-ef42-4808-b5a2-49501b24a37e`. It was claimed after **4.795s** and answered after **8.390s**. Result message: `fc236b62-b26d-5005-8d67-fac6c07a9836`.
Workers running immediately before refill: `codex` (`webchat-d10d5b84855a595ebae482626ddd0dec`).

### Earlier runs retained honestly

- The first post-hotfix group `max-376758688ad85272902ec5fc297a9b74` succeeded 6/6 with 12.312s five-worker overlap and a 3.530s refill claim.
- `max-e3b58c93173d5faaaf36247f4a0832be` completed 6/6 after the `BLOCKER: none` false failure caused Claude-to-Gemini retry. It was rejected by the strict original-worker proof and led to the parser correction.
- On final code, `max-0762639151ea5baf9ac1c88ec7ad60b4` completed all six on first attempts, but unrelated lane leases staggered starts. Its five-at-once assertion correctly failed; it is not counted as a concurrency PASS.
- After those tasks drained and leases became available, the final group above passed the strict concurrent-execution and original-worker completion checks.

## Reproduction and private evidence

```bash
python3 webchat/live_maxmode_proof.py run --root <live-data-root> --receipt <new-private-receipt.json>
python3 webchat/live_maxmode_proof.py verify --root <live-data-root> --receipt <saved-private-receipt.json>
python3 webchat/live_maxmode_proof.py refill --root <live-data-root> --receipt <new-private-refill.json>
```

The exact submitted multi-part prompt is the `PROMPT` constant in `webchat/live_maxmode_proof.py` and is also retained in the private receipt. It asks independent queue, integration, design, capacity and recovery analyses plus real local tests.

Runtime receipts stay outside Git: `conductor/state/webbob-maxmode-idle-proof-0927.json`, `webbob-maxmode-idle-refill-0927.json`, and `webbob-maxmode-final-deployment-0927.json`. Earlier receipts remain for comparison. No credentials, cookies or session files are committed.

The earlier parallel development run’s published commit was preserved, and the hotfix commits were rebased onto it before a normal fast-forward push. No PR merge, force push or Grok use occurred.

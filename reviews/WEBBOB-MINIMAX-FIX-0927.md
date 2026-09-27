OVERALL: PASS — API-only job prompts no longer assign a worktree, and rejected answers cannot become successful job results. Verified with real MiniMax/Gemini calls in an isolated data root. No live service was restarted or deployed.

Implementation commit: `f2af459` (`Fix API-only Web Bob prompts and reject unaccepted job answers`). Branch: `draft/webbob-minimax-0927`. Requested PR base: `draft/webbob-maxmode-0927`, at `fce1d5a3c11ae148bae69e0f770a814d73d2efe5` during verification.

The incident evidence was `../conductor/reviews/WEBBOB-VERIFY5-0927.md` and `../conductor/state/task-runs/webchat-d54cc740a7765f8e9def8b7e47caa0b8/RESULT.md`. MiniMax returned a filesystem refusal with the verification phrase appended, yet the dispatcher recorded success. Both the dispatcher and shared lane rules had introduced worktree instructions into an answer-only task. The old result check accepted any nonempty answer without an explicit `BLOCKER:` marker.

The fix separates API instructions from CLI rules. Gemini/MiniMax receive the task and supplied evidence, skip repository/worktree preparation, and persist `worktree: null` and `branch: null`. CLI tasks retain their existing worktree boundaries. Explicit file inspections route to Codex/Cursor with read tools; file changes require a writing CLI. A named API worker receives an honest capability explanation before any dispatch intent is saved. Queue validation, max-mode package validation and a guard for already-queued API tasks enforce that boundary. Required answer literals containing words such as `FIX` no longer misclassify confirmation tasks as coding.

Result acceptance happens before `succeeded` or `RESULT.md` is written:

- Empty answers, actual blockers, recognizable refusals and missing explicitly quoted required text are rejected deterministically. `BLOCKER: none`, quoted refusal examples and supplied code remain valid candidates.
- Other model answers undergo a separate task/answer review on the same worker lane, under its existing lease, budget and heartbeat. The review receives the complete task and candidate as data and must return a strict boolean JSON verdict with a reason. A refusal with a marker is insufficient, as is an unrelated answer containing the requested marker.
- Rejected answers and malformed/unavailable acceptance reviews terminate as `event: rejected`, `status: failed`, on the first unusable answer. Ordinary transport failures retain the existing bounded retry behavior. Redacted rejected output and the reason stay in the durable queue; chat delivers one failure instead of announcing completion.
- Accepted results include an acceptance receipt bound to the final answer SHA-256. Existing actual-file and local-test verification provide acceptance for small artifact tasks and Mini CPU work. File-content failures, unchanged files and unfinished code changes are terminal rejections.

The semantic review adds a model call for ordinary model jobs. It checks whether the answer completes the task; it is not independent proof of every factual claim. Natural-language file detection recognizes explicit access requests, while ambiguous tasks must still pass result acceptance. Claude acceptance context is bounded and is never silently truncated into an approving verdict.

Final full-suite validation:

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed**, 2.395 s |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **153 passed**, 12.775 s |
| `node --test webchat/test_quiet_hours_js.mjs` | **Passed**, 1 test |
| `python3 bootstrap.py check` | **syntax: PASS** |
| `git diff --check` | **Passed** |

Regression coverage includes the incident refusal plus marker, empty/blocker answers, missing exact text, generic help, plans instead of results, unrelated answers, invalid verdict types, review transport failure, stale success after rejection, file routing, explicit max-mode file packages, verification literals containing `FIX`, and exactly-once failed-result delivery after restart. Existing lease fencing, concurrency, outage retry, artifact writes and CPU tests remain covered. Service-test log lines describing restarts come from mocked watchdog tests, not live service operations.

Final isolated proof ran **2026-09-27 18:32:02–18:32:26 UTC**. See [raw evidence](WEBBOB-MINIMAX-FIX-0927.evidence.json) and the [reproduction script](WEBBOB-MINIMAX-FIX-0927.proof.py). The evidence includes source-file hashes matching all six final implementation files, full isolated queue transitions, acceptance receipts, result hashes, chat messages, timings, budget deltas and the live listener identity before/after.

Positive cases submitted real jobs through an isolated `Chat`, claimed the named worker and ran the unmodified `services/dispatch-worker.sh` launcher with real API transport. No provider output was mocked for those cases. Their successful replies were:

| Worker | Job | Time including acceptance | Actual answer |
| --- | --- | ---: | --- |
| MiniMax | `webchat-97e2496753a35cd19b995dcb1ab06f02` | 17.861 s | I confirm that I ran the assigned task, WEBBOB-MINIMAX-FIX-0927-bab99035 minimax. |
| Gemini | `webchat-5d18cfcf116256c696826a4f415862da` | 1.160 s | I ran, WEBBOB-MINIMAX-FIX-0927-bab99035 gemini. |

Each had one attempt, a positive task-specific acceptance verdict, one successful chat result, a matching persisted `RESULT.md` and SHA-256, and no worktree or branch. No `workspaces` directory was created in the isolated root.

Negative proof cases:

| Case | Job / result |
| --- | --- |
| Replay the exact saved incident refusal as the candidate answer | `webchat-4170345fc74d56f0b7ae4fbe6713583f`: **failed** after 1 attempt; no acceptance call needed |
| Inject an answer about tomatoes with the required marker into a `12 + 18` task; use the real MiniMax acceptance reviewer | `webchat-e4001760e78a53cdbd2481db2a44e062`: **failed** after 1 attempt; reviewer identified the missing sum `30` |
| Ask named MiniMax and Gemini workers to read `services/dispatch_worker.py` | Both refused before enqueue with the explicit API-only capability explanation |

The two rejected jobs have no successful transition or `RESULT.md`, and each delivered exactly one failed chat result. The negative candidates were deliberately injected/replayed to exercise rejection; the off-topic acceptance verdict came from a real API call.

The final proof used five metered API calls: three MiniMax calls costing $0.00215130 and two Gemini calls costing $0.00031410. Existing live spending records were copied into the isolated ledger before calling providers; live ledgers, queues, conversations, deployment pins and service locks were not modified. Credentials were held in the process environment and removed from persisted proof output.

The live listener remained **PID 99149**, started **Sun Sep 27 12:40:03 2026 America/Chicago**, running `workspaces/webbob-integrate-0927-service/webchat/app.py`, before and after both isolated proof runs. No restart, live deployment, merge, force-push or Grok invocation occurred.

Reproduction from this checkout, with the existing local credentials available:

```sh
set -a
. ../conductor/keys.env
set +a
python3 reviews/WEBBOB-MINIMAX-FIX-0927.proof.py "$PWD"
```

The script allocates a temporary data root, uses a provider stub only to forbid ordinary conversational generation, and uses real worker calls for the positive cases. It reads the incident result and live listener identity for comparison, then writes its evidence to this review directory. The live deployment remains on its existing checkout.

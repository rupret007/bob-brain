# Cross-vendor reply-quality review

Reviewer: Codex. Candidate authored by Claude: `15d0ff4`, based on live
`dff84e3`. Branch remains `draft/webbob-replyq-1856`; draft PR #14 remains draft.

The initial candidate did not meet Jeff's bar. These findings were repaired
on that branch before the deployment gate:

1. Dropping "Yes" and shortening a log excerpt did not remove the dump.
   Casual status now uses at most four full sentences, groups actual worker
   tasks, names observed models, and reserves IDs, log paths and raw output
   for requested diagnostics. Missing metadata is stated honestly. Busy
   cached lanes and unreadable queues do not become idle/empty claims.
2. The prompt's "snapshot always has something concrete" could encourage
   invention and contradicted the context's instruction to paste logs.
   Both instructions now agree with the formatter. Model metadata can be
   recovered from a fresh CLI startup header; old logs and prose mentioning
   models are not evidence. An unreported exact model remains unreported.
3. Queue receipts exposed internal IDs and were rewritten as "Finished" at
   their original submission timestamps. Receipts now name the requested
   task and worker in full sentences and stay unchanged across claims,
   completion, retries and reload. Live job state stays in structured job
   data; completion has its own timestamp. Verified project publications
   name the actual worker and link the resulting SHA in one sentence each.
4. The eval returned success with a failure, three checks used `or True`,
   and a worktree path check substituted for song persistence. The eval now
   uses isolated data, actually saves/reloads a song, evaluates every case,
   and exits unsuccessfully if any of its 33 cases fails. The self-awarded
   "beat Bob" score was removed; no direct model comparison was performed.
5. Old tests asserted the undesirable dumps and mutable receipts. They now
   assert factual task/model/time attribution, four-sentence status,
   diagnostic opt-in, redaction, immutable receipts and real queue effects.
   New release tests prove that queued/claimed jobs cannot count as actual
   execution and that a bad live build identity triggers a verified rollback.

Validation command: `bash reviews/run-webbob-tests.sh`, followed by
`python3 webchat/bob_parity_eval.py`. The committed SHA and exact final suite
results are stored in `webchat/evidence/replyq-tests.json` before release.

Deployment uses the prior parity pass's code-root pins and supervisor-locked
restart of only webchat/job-runner. A fresh `rollbacks/webbob-replyq-<timestamp>`
snapshot precedes the pin change. `webchat/deploy_replyq.py` verifies local
and public version identity, replays every user turn from the latest three
saved sessions in new conversations, checks each reply, and waits for actual
execution of every requested project job in its own draft worktree. Any
failure restores the snapshot and verifies the old SHA. The gate never
merges or undrafts, prints credentials, or creates a STOP file.

Offline prompt checks are not proof of free-text model quality. The live
greeting and all 16 original turns must also pass before the reviewer writes
`conductor/LOOP-REPLYQ-LIVE-0927.txt`. No live pass is claimed by this review.

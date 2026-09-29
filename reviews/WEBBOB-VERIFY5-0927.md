OVERALL: FAIL — all five worker lifecycle/identity checks passed, but MiniMax returned a refusal instead of the requested confirmation while the server marked its job succeeded.

Independent acceptance test of the live Web Bob at `http://127.0.0.1:8787` on 2026-09-27. Live observations: 2026-09-27T17:58:34.419Z through 2026-09-27T17:59:57.482Z; final persisted-record verification: 2026-09-27T18:01:27.975Z.

Authenticated using `conductor/webchat/.password`, held only in memory and never printed. Created new empty chat `0f27dc01-d1aa-476b-bd78-4d9946c749e9` through `POST /api/conversations`; all test messages went to this chat. No existing Jeff conversation was used. No application code was changed and no service was restarted. The listener remained PID `99149`, started at 12:40:03 America/Chicago, running `workspaces/webbob-integrate-0927-service/webchat/app.py`.

Read the login, message, dispatch, and result-delivery handlers. Used form `POST /login`, authenticated `GET /api/session` for CSRF, JSON `POST /api/messages`, and `GET /api/conversations/<id>` for receipts/results. Each worker request supplied the exact `worker` field, with `provider: "auto"` (the separate conversational-provider selector). Queue evidence was parsed directly from `conductor/state/queue.jsonl`; no app test helpers, mocked providers, or direct queue writes were used.

Each worker received this real chat request, substituting its name:

```text
start a job: write one sentence confirming you ran, into your answer. Include the exact phrase 'WEBBOB-VERIFY5-0927-d8f5a3e9 <worker>'.
```

Worker acceptance requires the requested confirmation as well as the queue/claim/completion/chat-identity checks. “Lifecycle/receipt” below isolates the explicit queue checks: the job exists, every claim names the requested worker, execution and successful finish are recorded, and the completed chat reply contains that same real job ID and worker. All five passed those checks. MiniMax fails the answer check; its API execution and routing are not in dispute.

All claim times below are UTC on 2026-09-27. “Finish seconds” is `finished_at - created_at` from the queue, including waiting; “After claim” is `finished_at - claimed_at`.

| Worker | Verdict | Job ID | Claim time (UTC) | Finish seconds | After claim (s) | Lifecycle/receipt |
| --- | --- | --- | --- | ---: | ---: | --- |
| codex | **PASS** | `webchat-a0eee97f6aff5f8098916e3edcf7da1d` | 17:58:38.923 | 8.172 | 5.999 | PASS; exact `codex` claim |
| claude | **PASS** | `webchat-2bbd4e4fd3195866abe41e1a758c6129` | 17:59:33.658 | 79.671 | 22.802 | PASS; exact `claude` claim |
| gemini | **PASS** | `webchat-3b41c30c9a755e26beba0fca6abdb678` | 17:58:38.953 | 3.301 | 1.175 | PASS; exact `gemini` claim |
| minimax | **FAIL** | `webchat-d54cc740a7765f8e9def8b7e47caa0b8` | 17:58:38.976 | 9.525 | 7.412 | PASS; exact `minimax` claim |
| cursor | **PASS** | `webchat-99ce71e0b0d85fabb29ebf245431333b` | 17:58:38.997 | 11.703 | 9.608 | PASS; exact `cursor` claim |

Each job had one attempt, a recorded worker PID and execution timestamp, exactly one completed chat result, a matching result SHA-256, matching `conductor/state/task-runs/<job-id>/RESULT.md`, and a durable delivery event. Claude waited 56.868 seconds before its claim; its worker then completed in 22.802 seconds.

Queue evidence (one-based line numbers in [queue.jsonl](../state/queue.jsonl)):

| Worker | Enqueued | Claimed | Executing | Succeeded | Delivered |
| --- | ---: | ---: | ---: | ---: | ---: |
| codex | 695 | 700 | 708 | 714 | 715 |
| claude | 696 | 720 | 722 | 725 | 726 |
| gemini | 697 | 701 | 709 | 712 | 713 |
| minimax | 698 | 702 | 710 | 716 | 717 |
| cursor | 699 | 703 | 711 | 718 | 719 |

The final chat reply for every worker begins `Job <its job ID> finished on <its worker>:` (with the ID rendered in backticks). Actual worker answer excerpts:

| Worker | Returned answer |
| --- | --- |
| codex | I ran and confirm WEBBOB-VERIFY5-0927-d8f5a3e9 codex. |
| claude | I ran successfully — WEBBOB-VERIFY5-0927-d8f5a3e9 claude. |
| gemini | I ran the task. WEBBOB-VERIFY5-0927-d8f5a3e9 gemini |
| minimax | “I cannot access or work with the Git worktree … or perform the described actions …” followed by generic offers of help and a “Verification phrase” containing the run marker. |
| cursor | I ran the Web Bob verification task in the assigned worktree and include the exact phrase **WEBBOB-VERIFY5-0927-d8f5a3e9 cursor** in this confirmation. |

MiniMax failure: the task asked only for a sentence in the answer. Its result instead refuses filesystem/worktree actions that were not requested. The dispatcher still recorded `status: succeeded`, and chat announced “finished on minimax.” The full refusal is preserved in the evidence JSON and the worker’s [RESULT.md](../state/task-runs/webchat-d54cc740a7765f8e9def8b7e47caa0b8/RESULT.md). This is an answer-acceptance failure despite passing all routing, lifecycle, and receipt checks.

Provider status: **PASS**. Sent `What is the current chat provider status for codex, claude, gemini, minimax, and cursor?` in the test chat. The server replied at `2026-09-27T17:58:36+00:00`:

> Chat provider health: codex=ready; claude=ready; cursor=ready; gemini=ready; minimax=ready.

| Provider | Health file | Chat reply | `/api/lanes` | Verdict |
| --- | --- | --- | --- | --- |
| codex | ready | ready | ready | PASS |
| claude | ready | ready | ready | PASS |
| gemini | ready | ready | ready | PASS |
| minimax | ready | ready | ready | PASS |
| cursor | ready | ready | ready | PASS |

Compared against `conductor/webchat/sessions/provider-health.json` read immediately before and after the status turn; the file entries were stable. Every provider had zero failures, no reason/cooldown, and a recorded last success. All persisted health fields also matched the authenticated `/api/lanes?conversation_id=<test-chat>` response. This verifies chat generation health; scheduler lane occupancy is a separate state.

No-job queue claim: **PASS**. Before submitting any jobs, the first message in the empty new chat was exactly `did you queue it`. The answer began:

> No, I didn't queue anything in this turn.

There were zero queue rows for this conversation before and after that turn, no new job IDs anywhere in the queue during it, no task ID, and no queued action card. The reply did not falsely claim that a job was queued. Its additional statement “I can't directly queue jobs from this chat” is misleading capability wording, as the subsequent five dispatches demonstrate; it does not change the no-false-queue result.

Complete raw requests, accepted receipts, completed chat messages, queue transition rows with line numbers, health snapshots, HTTP statuses, timing calculations, result-integrity checks, and service identity are saved in [WEBBOB-VERIFY5-0927.evidence.json](WEBBOB-VERIFY5-0927.evidence.json). No credentials or authentication tokens are included.

# Web Bob clean chat — 2026-09-27

PASS. Ordinary replies have no job disclaimer or command-syntax footer. Natural work requests use the real durable queue and receive one short receipt after the server confirms the write. Ambiguous requests get one short question.

Base: `draft/webbob-maxmode-0927` (`fce1d5a3c11ae148bae69e0f770a814d73d2efe5`). The change is limited to chat wording, intent detection, their tests, and this proof. Worker prompts, queue internals, and result acceptance have no diff from the base. Nothing was deployed or restarted.

## Behavior

- `fix X`, `review PR #161`, and `have Claude do Y` dispatch without a second confirmation, including polite prefixes.
- `go` accepts one current concrete offer or saved proposal. Missing context, alternatives, missing prerequisites, old offers, and a repeated `go` after dispatch ask for the task without creating another job.
- Queue receipts say `Queued — job <id>.` or `Queued for Claude — job <id>.` only after enqueue returns. A recorded worker claim changes the receipt to `Started on Claude — job <id>.` Queue-save failures produce no success receipt.
- Ordinary answers retain their text and formatting. Unsupported model claims and unsolicited job notices are removed without a replacement footer. Style preferences receive a brief acknowledgement. Explicit operational questions still use server state.
- Existing worker capability restrictions, Grok rejection, saved intent, retries, duplicate-request protection, legacy proposal IDs, and result delivery remain intact.

## Full-suite validation

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **98 passed**, 3.129 s |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **163 passed**, 25.362 s |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `python3 bootstrap.py check` | **syntax: PASS** |
| Python compilation of changed runtime files and proof harness | **Passed** |
| `bash -n webchat/start.sh webchat/run.sh launchd/install.sh` | **Passed** |
| `git diff --check` | **Passed** |

Total: **261 Python tests**. Coverage includes false job claims, preserved normal answers and formatting, natural routes, contextual and ambiguous follow-ups, worker claims, failed queue writes, duplicate requests, interrupted saves, and recovery. An earlier concurrent run hit a transient macOS PermissionError in the existing child-process cancellation test; the complete final suite passed, including that test. Service-test lines about restarting a reviewer are mocked watchdog checks, not live restarts.

## Six isolated live examples

Ran `2026-09-27T18:53:45.467517+00:00` through `2026-09-27T18:54:02.119724+00:00` at `http://127.0.0.1:58446` with a fresh private data root. These are authenticated HTTP login, POST, polling, and jobs API requests against the real `Chat` and `Server`, with two real Claude chat calls and real queue writes. No provider or queue was mocked.

| # | Context | Message | Exact visible reply |
| --- | --- | --- | --- |
| 1 | direct request | `Keep replies short and friendly.` | Got it. |
| 2 | direct request | `fix the login button` | Queued — job webchat-ecad3214af5c5c9a9042c1ebee0aff05. |
| 3 | direct request | `review PR #161` | Queued — job webchat-d910baca01b854e893c783f8490d59c1. |
| 4 | direct request | `have Claude review PR #161` | Queued for Claude — job webchat-1f7a606921925452aac4d8d71e65dc60. |
| 5 | fresh conversation | `go` | What would you like me to work on? |
| 6 | current proposal below | `go` | Queued — job webchat-b0924d422e9e545fb29d5722202cf206. |

Example 6 used this additional setup turn in its own conversation:

- Message: `Can you offer to review PR #162 in rupret007/bob-brain in one short sentence?`
- Real Claude reply: “I can offer to review PR #162 in rupret007/bob-brain — want me to take a look?”

All four returned IDs existed in the fsynced queue journal and `/api/jobs`, with matching conversation and request IDs. Replaying each request through HTTP produced the same ID and no extra row. Ordinary chat and the ambiguous `go` created no rows. All four rows remained `queued`, with zero attempts and no claimed worker: this proof covers chat and submission, not worker execution. The short `Started on …` update is separately verified against actual queue claim/running transitions in the regression suite.

| # | Conversation ID | Request ID |
| --- | --- | --- |
| 1 | `6ad98a55-5638-4106-a8d5-f2964ce95946` | `48a26261-1036-4d15-adc5-571f390dcf31` |
| 2 | `3d1f2731-5daf-4991-8c9f-e9e0ea5531f5` | `ed93202c-66a4-4acf-83f2-43dad0c084f2` |
| 3 | `4032a048-dbc2-4ce4-94e8-f9f919923b83` | `e55c2d56-1049-49d0-9d15-a73f50a0f0ba` |
| 4 | `f9fca2cd-f623-48b0-9d8d-90f50679d1e3` | `27650675-1e58-4423-807c-063c00e1566b` |
| 5 | `71ea1ef2-2a0a-4345-975b-2bc701276729` | `c72f4e42-8bcc-47b8-9e9a-f08a7897407c` |
| 6 | `8a9e0321-4636-4b30-ab57-73b14699dbff` | `25893aec-2840-450e-a36e-556e0d1e9acf` |

## Isolation and evidence

The harness creates a temporary private root and an ephemeral loopback listener, then closes only its own server. It starts no worker runner. All seven live service screen identities were identical before and after:

- `17509.svc-dashboard-updater`
- `45974.svc-reviewer`
- `53542.svc-watchdog`
- `69790.svc-project-tick`
- `77277.svc-webbob-reviewers`
- `94801.svc-disk-watch`
- `99081.svc-job-runner`
- `99147.svc-webchat`

Private receipt: `/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/webbob-clean-proof-1y3ue2jb/proof.json`. The receipt contains source hashes matching the final runtime files, all example replies, request IDs, queue rows, and service identities. Passwords and cookies are not logged or committed.

Queue journal SHA-256: `7a48a51815806fcb08271ea6f7f53002f329ed278a7273cdb9688aa8d3fc0fca`.
Receipt SHA-256: `7203a56276e2f5a04b08e70e5374e0b1556a5a778ce5d9e9d1d27b9a8c755cf5`.

Reproduce from the repository root:

```bash
python3 webchat/live_clean_proof.py --provider claude
```

The CLI prints the six example replies, the context-setting turn, and the private receipt path. Each run creates its own data root and leaves live services alone.

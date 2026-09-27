# Web Bob hotfix — 2026-09-27

PASS: real chat requests produced durable queue records, real CLI execution, verified file writes and one result in the originating conversation on Codex, Cursor and Claude. All three completed in under two minutes, including the entire sequential three-worker run.

## Incident and repair

The 12:06–12:14 CT conversation `2bd59fcd-cb1d-40e5-adcf-2da66824ec88` contains a Gemini reply claiming a builder-inbox write without a queue receipt. The work parser missed “Ok figure out …”. Later Gemini replies identified Cursor as answering and repeated old Gemini/MiniMax failures even though current health records and production success events showed recovery.

- Conversational action prefixes and “figure out / diagnose / improve” now reach the saved dispatch-intent and fsynced queue path. Builder-inbox requests that contain executable work use the same dispatcher.
- Queue acknowledgments are server generated only after enqueue returns. They include the durable job ID. Claimed/running updates add the actual worker; terminal answers include both ID and worker. Disk-write failures never produce a successful receipt, and saved intent/outbox delivery recover idempotently.
- Every model attempt receives its actual provider and fresh generation health. Retry prompts refresh status. The snapshot reads `conductor/webchat/sessions/provider-health.json` and bounded production events from `logs/webchat-failover.log`; successful probes are not treated as successful generation, and injected/drill failures are excluded.
- Operational status prose is generated from server state, including the actual answering provider for forced model replies. Unsupported model claims of queued work are rejected by the reply guard.
- Explicit small text writes to named `/tmp` text artifacts execute through tool-capable CLI workers, including Claude. The worker must change the file and its contents must match before success is persisted. General coding remains on Codex/Cursor. Markdown BLOCKER headings are failures, not successful answers.

## Validation

- `python3 -m unittest discover -s services -p 'test_*.py'`: **94 passed**.
- `python3 -m unittest discover -s webchat -p 'test_*.py'`: **144 passed**.
- `node --test webchat/test_quiet_hours_js.mjs`: passed.
- `python3 bootstrap.py check`, all shell syntax checks and `git diff --check`: passed.
- Regression coverage includes the exact incident wording, durable claim updates, queue write failure, generation recovery versus probe health, false provider identity/queue claims, and refusing false file-write success. No paid calls are used by unit tests.

## Deployment

Tested code: `ed3d689740c28dc1eddd85b19b08ec3da1b78687`. Activated `2026-09-27T17:27:17.667278+00:00`.
Code root: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-0927-service`. Both runtime pins point there. Live data and credentials remain in the existing conductor root.
Only `svc-webchat` and `svc-job-runner` were restarted. The before/after receipt confirms every other screen identity stayed unchanged.
An older max-mode run was concurrently using the original worktree and repointing the services. This hotfix was completed in an isolated worktree, then activated in the requested integrate service checkout under the supervisor/startup locks. No unrelated process was stopped.

## Live proof

Command: `python3 webchat/live_hotfix_proof.py --root ..` from the hotfix worktree. The harness authenticates with the existing password in memory, submits through `POST /api/messages`, and polls the chat API and durable journal. It never manually enqueues, claims, completes, inserts chat results, or writes the proof target.

Exact message, repeated for each explicitly selected worker: `start a job: write hello to /tmp/wb-proof.txt`.

| Worker | Job ID | Queued UTC | Claimed UTC | Finished UTC | Answered UTC | End-to-end |
|---|---|---|---|---|---|---|
| codex | `webchat-49a1653265f556ab9bed15eb8a498f23` | 2026-09-27T17:27:22.492+00:00 | 2026-09-27T17:28:27.011+00:00 | 2026-09-27T17:28:35.872+00:00 | 2026-09-27T17:28:35.974+00:00 | 73.481s |
| cursor | `webchat-5c84b1ac3d265eee8d1cec0e362f41ae` | 2026-09-27T17:28:36.011+00:00 | 2026-09-27T17:28:40.717+00:00 | 2026-09-27T17:28:51.115+00:00 | 2026-09-27T17:28:51.845+00:00 | 15.834s |
| claude | `webchat-295c8c9903f454dc9bde904cc103824e` | 2026-09-27T17:28:51.889+00:00 | 2026-09-27T17:28:54.276+00:00 | 2026-09-27T17:29:01.507+00:00 | 2026-09-27T17:29:02.402+00:00 | 10.514s |

Total from first submission to third chat answer: **99.910s**. Codex waited behind the earlier max-mode run; its actual execution still completed within the two-minute end-to-end limit.

### codex
Conversation: `c9506312-ea3f-44a6-bd6b-ee2500fc7b24`. Result message: `69aa4153-afe7-5717-a534-4d165abc2c53`.

Journal: enqueued → claimed → running → executing → succeeded → delivered

Actual final chat answer:

```text
Job `webchat-49a1653265f556ab9bed15eb8a498f23` finished on codex:

Wrote and verified `hello` in [/tmp/wb-proof.txt](/tmp/wb-proof.txt).

Server verified file: /tmp/wb-proof.txt; SHA-256: 5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03
```

### cursor
Conversation: `d9a540fd-5245-423c-9857-d90776f4f1a0`. Result message: `7fa50495-bfef-5932-acd1-18f8cef63ddd`.

Journal: enqueued → claimed → running → executing → heartbeat → succeeded → delivered

Actual final chat answer:

```text
Job `webchat-5c84b1ac3d265eee8d1cec0e362f41ae` finished on cursor:

Wrote `hello` to `/tmp/wb-proof.txt` and verified the contents. Path: `/tmp/wb-proof.txt`. No repository changes.

Server verified file: /tmp/wb-proof.txt; SHA-256: 5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03
```

### claude
Conversation: `7f015a4a-db6a-4f38-bc46-2f355e3d7197`. Result message: `f0d94236-9258-581a-878e-4e539e00f00e`.

Journal: enqueued → claimed → running → executing → succeeded → delivered

Actual final chat answer:

```text
Job `webchat-295c8c9903f454dc9bde904cc103824e` finished on claude:

Wrote "hello" to `/tmp/wb-proof.txt`, confirmed written. No repository changes made.

Server verified file: /tmp/wb-proof.txt; SHA-256: 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
```

## Provider proof

Forced `gemini`; conversation `f8aed2cb-33e9-4d5f-a99a-10b94aa8e918`, request `96610b26-0a33-4c06-b6f4-a3b81e335510`, verified `2026-09-27T17:29:04.689+00:00`.

```text
Answering provider: gemini. Server status at 2026-09-27T17:29:04+00:00.

Chat provider health: codex=ready; claude=ready; cursor=ready; gemini=ready; minimax=ready.
```

Forced `minimax`; conversation `ddc43cc0-2edc-46ed-a7db-20fc68a138df`, request `1ec1360c-8ae7-4fcf-b3d9-e5d3dbb5c0df`, verified `2026-09-27T17:29:10.054+00:00`.

```text
Answering provider: minimax. Server status at 2026-09-27T17:29:09+00:00.

Chat provider health: codex=ready; claude=ready; cursor=ready; gemini=ready; minimax=ready.
```

Runtime evidence stays outside Git in `conductor/state/webbob-hotfix-proof-0927.json` and `conductor/state/webbob-hotfix-deployment-0927.json`. No password, cookies, tokens or keys are included here.

## Final follow-up

The max-mode follow-up passed 246 tests (98 services, 148 webchat) and was deployed as `570bc5af223f87c1b149caa7bf9d8d3cb3b75359` from the same integrate service checkout. Original three-worker hotfix answers were verified unchanged and present exactly once after the subsequent restart. The final code also distinguishes `BLOCKER: none` from a genuine failure. See [WEBBOB-MAXMODE-0927.md](WEBBOB-MAXMODE-0927.md) for the final deployment and fan-out evidence.

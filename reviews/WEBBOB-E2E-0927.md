# Web Bob end-to-end proof — 2026-09-27

Final verification: **PASS**. Public address: https://jeffs-mac-mini.tail758ab4.ts.net. Local listener: http://127.0.0.1:8787. All times below are UTC; Chicago is UTC−05:00 on this date.

## Running release

- Code: `/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927` on local branch `draft/webbob-e2e-0927`. The exact tested files are identified by [e2e-0927-tested-manifest.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-tested-manifest.json). Tested changes remain uncommitted in this isolated worktree. A verified source snapshot is archived alongside the proof; the mutable shared checkout is not the deployed release.
- Data: `/Users/jeffstory/Documents/bob-overnight-inject`. The existing password, conversations, budgets and durable task journal are preserved in `conductor`; credentials were not changed.
- Installed LaunchAgent: `/Users/jeffstory/Library/LaunchAgents/com.jeff.bob-webchat.plist`. It starts this release with `BOB_ROOT` set to the original data root, its dispatcher enabled, and production fault injection disabled.
- Final controlled restart: 2026-09-27T15:54:38+00:00 → 2026-09-27T15:54:39+00:00; listener PID `405`. Both full suites passed before this restart. Only `svc-webchat` and its own launcher were restarted by this E2E task.
- Both shared start/run scripts also select this release through `state/webchat-code-root`; actual launcher probes verified this takes priority over the older dispatch-only setting. The existing job-runner release selection is preserved.
- Deployment and source-hash receipt: [e2e-0927-deploy.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-deploy.json). Tested source snapshot: [webbob-tested-source-0927.zip](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/webbob-tested-source-0927.zip) and [e2e-0927-source-archive.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-source-archive.json).

## Actual public chats and phone checks

Each row below used a fresh authenticated HTTP conversation and a real model answer explaining how to check chat persistence. The harness rejects canned local replies and asserts the selected provider actually answered.

| Selected provider | Answering provider | Seconds |
|---|---|---:|
| codex | codex | 6.97 |
| cursor | cursor | 8.68 |
| gemini | gemini | 1.42 |
| minimax | minimax | 4.26 |
| claude | claude | 7.23 |

Public provider and memory proof: [e2e-0927-public-providers.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-public-providers.json). The second memory turn correctly recalled the imaginary boat Copper Heron and the earlier motto.

- WebKit: **14 checks passed**. [e2e-0927-webkit-final/proof.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-webkit-final/proof.json).
- Chromium: **14 checks passed**. [e2e-0927-chromium-final/proof.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-chromium-final/proof.json).
- Both browser engines visited the Tailscale HTTPS address, rejected a wrong password, logged in, checked Secure/HttpOnly/SameSite cookies, sent real chats from the composer, reloaded saved history, used the job chip, executed uptime and repository status, refused force-push, dismissed council approval, stopped a real reply request with Codex selected, visited every bottom tab, and logged out with subsequent API access returning 401.
- Viewports: 390×844 and 430×932 with touch/mobile enabled. No horizontal document overflow, browser exceptions or HTTP 5xx in the final passing runs. Screenshots were inspected for visible text and reachable controls: [e2e-0927-webkit-final/chat.png](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-webkit-final/chat.png), [e2e-0927-chromium-final/chat-large-phone.png](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-chromium-final/chat-large-phone.png).
- These are real browser engines running on the mini. A physical phone and cellular network were not available for this session; that last device/network check is not claimed.

## Failover and history durability

**17 live checks passed** on a temporary local server using the same chat/provider code and real credentials. Fault injection was scoped to test conversations; production drill routes remain disabled. Every successful fallback made an actual model call. [e2e-0927-isolated.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-isolated.json).

| Injected primary failure | Real answering provider |
|---|---|
| codex | cursor |
| cursor | codex |
| gemini | codex |
| minimax | codex |
| claude | codex |

Additional failures of the entire preceding chain reached Gemini, MiniMax and Claude. All five failing saved a waiting turn; clearing the faults and retrying produced exactly one answer, with the original two-message conversation intact.

The preexisting audit conversation `ce987867-6a68-4140-a314-364e373956b9` retained its 2 messages byte-for-byte across the final service restart. The previous cookie was invalidated, fresh HTTPS login succeeded, and saved conversations and completed lane answers were reread afterward. [e2e-0927-final-history.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-final-history.json).

## Commands, repository status and a real lane

The mobile tests actually ran `uptime` on the mini and `git status --short --branch` in the configured conductor repository, with exit-zero receipts and provider `mini`. Shell operators, credential reads, arbitrary repository paths and Git mutations are refused. Larger jobs use the durable task dispatcher.

Through the public chat API, `start lane gemini: E2E0927 read-only review…` created task `webchat-de836fc057e05162994c45ffdfa1afba` in conversation `0fd88d64-be56-4d25-b18d-4c1f43571736`. The real Gemini worker completed it in 1 attempt(s), and exactly one result appeared in that same chat. Repeating the HTTP request ID created no duplicate execution.

- Claimed: 2026-09-27T15:54:56+00:00; execution: 2026-09-27T15:54:56+00:00; finished: 2026-09-27T15:54:58+00:00; delivered: 2026-09-27T15:54:58+00:00.
- Result SHA-256: `514d96c2f7bf007a122457d5983c2c3aa224fb3790b247a6f0d83351227f483f`; draft branch: `draft/webchat-de836fc057e05162994c45ffdfa1afba`.
- Receipt and actual answer: [e2e-0927-public-lane.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-public-lane.json). No direct queue insertion or manual completion was used.

## Defects repaired and regression coverage

1. Added Claude to the full provider chain and all five primary choices; fixed exhausted fast-path timing that could skip or repeat providers. Claude receives prompts on stdin rather than process arguments.
2. Added bounded, redacted mini-command and repository-status execution with real exit receipts, durable history and request deduplication. Unsupported commands are visibly refused.
3. Fixed the Start job chip and council phrasing. Explicit lane requests reach the durable dispatcher. A read-only review saying “Do not change files” stays an analysis task.
4. Integrated durable claims, lease recovery, lane selection, result delivery to the original chat and delivery deduplication. Legacy Web Bob queue rows cannot start a second execution. Fixed duplicate sidecar-field handling in the legacy scheduler.
5. Corrected code imports that depended on the data checkout or test fixture. Launchers, API transport, dashboard modules and detached workers now load the selected release while reading the original data root. The web service has its own dispatcher; its lock coordinates with the job runner. Coding workers cannot modify the running release.
6. Disabled production drills by default. A slow health probe no longer kills an existing service. The restart helper requires authenticated idle status and verifies the exact listener before stopping it.
7. Added private exception-type auditing without logging exception text, prompts or credentials. Secrets, sessions, evidence and worker outputs are excluded from Git.

Final offline gate: **274 passed** (170 webchat + 104 services). Python compilation, JavaScript syntax, launcher shell syntax and `git diff --check` passed. The gate hashes the code before and after tests and refuses a restart if files changed. [e2e-0927-test-gate.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-test-gate.json), [e2e-0927-webchat-tests.txt](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-webchat-tests.txt), [e2e-0927-services-tests.txt](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-services-tests.txt).

## Deployment interference, logs and secrets

Independent workers switched/reset the shared checkout and replaced `svc-webchat` during this task. An early passing run therefore ceased to describe the live application. The tested work was recovered without dropping the stash or overwriting their changes and moved into the isolated release above. Interrupted public/browser runs returned 502 and were treated as failures, retained privately, and rerun after the final controlled deployment. They were not counted as passes.

The automatic deployment loop also kept selecting older code. Its existing `~/STOP-WEBBOB` flag is now set to prevent new rounds. After waiting for the current round, its Cursor/MCP/tool processes and the overlapping integration worker were paused with SIGSTOP, without termination, to prevent further deployments. They retain their process state; their files and other workers were preserved. Twelve process identities were preserved in total; the audit worker had no matching live agent to pause. The flag and pauses are intentionally left in place to keep phone chat stable. Before resuming automatic deployments, carry these tested fixes into the improvement branch. Pause receipt: [e2e-0927-autopilot-pause.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-autopilot-pause.json). A PID/start-time/command-verified resume helper is [resume-paused-improvement.py](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/resume-paused-improvement.py); use `--resume` only after coordinating the next deployment. It keeps the stop flag for later rounds.

Final log audit: no runtime error/exception/traceback/failed/permission-error lines in active `logs/webchat-*.log`; no provider failure, all-down, request/reply/queue/dispatch error events since the final restart. Expected cancellation/refusal events are retained. [e2e-0927-logs.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-logs.json).

A public rerun selected MiniMax during an existing network cooldown and correctly received a useful Codex fallback. That run was not counted as a successful MiniMax primary check; the cooldown was allowed to expire before retrying. Receipt: [e2e-0927-public-cooldown-fallback.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-public-cooldown-fallback.json).

The failover audit retains historical events: {'live-drill': 33, 'production': 9}. These predate the final restart and are disclosed rather than erased. The separate earlier launchd permission-error log was preserved at `/Users/jeffstory/Documents/bob-overnight-inject/logs/archive/webchat-launchd-before-e2e-0927.log` (SHA-256 `6c58064737c4c14b281b1f6b610def83eeaa454a235866060d134ddb31e06781`); it contains 302 old error lines, followed by healthy checks. The active launchd log retained the subsequent healthy history.

Known-secret scan: 814 Git-visible files checked against 3 actual secret values; zero matches. [e2e-0927-secret-scan.json](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/evidence/e2e-0927-secret-scan.json). Passwords, cookies, CSRF tokens and API keys are absent from this report and were not added to Git.

No merge, push, force-push, undraft, external message, or remote PR action was performed by this E2E task.

## Use from the phone

Open the Tailscale URL and use the existing Web Bob password. Try `run command: uptime`, `repo status: conductor`, or `start lane gemini: review these notes…`. Settings selects the first provider; failures fall through the remaining chain. Saved conversations are available from the chat icon.

Reproduction and release-start commands are in [/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/README.md](/Users/jeffstory/Documents/bob-overnight-inject/worktrees/webbob-e2e-0927/webchat/README.md).

# Web Bob redeploy failed — 2026-09-27

**Final result: FAIL. Rolled back successfully. No ready-to-test handoff was written.**

Candidate SHA: `7c9ed942c03a8678fc189a123c5e151c80ddf6c3`  
Draft PR: https://github.com/rupret007/bob-brain/pull/10  
Branch/worktree: `draft/webbob-redeploy-0927` / `wt-webbob-redeploy-0927`  
Fresh rollback: `/Users/jeffstory/Documents/bob-overnight-inject/rollbacks/webchat-20260927-160618`

## Exact failing check

**`claude161` failed execution.** The literal ask `have Claude review PR #161` created a real durable job and was claimed by Claude. Claude exited with code 1. The scheduler retried on Gemini, which could not access the PR. Result acceptance rejected that answer and delivered a failed-job message. The journal does not record a more specific cause for the Claude CLI exit; it must not be guessed.

Job: `webchat-2fbdaf20f5a453a1a0af6c88fea5f0f9`

> Worker reported a blocker: BLOCKER: I need access to the pull request system to review PR #161. I do not have the capability to access external systems or web pages.

| Live check | Initial authenticated acceptance | Final evidence |
| --- | --- | --- |
| `going`: `is it going now?` | PASS | Server reported the two actual Codex lanes, Fantasy audit and Web Bob redeploy. Detailed follow-up included all stable worker/service screens. No status job was created. |
| `claude161`: `have Claude review PR #161` | PASS | **FAIL** after execution: Claude exit 1, Gemini fallback lacked PR access, result rejected. |
| `push2`: `push WebJam and AdoptIQ` | PASS | Two real coding jobs, claimed by Codex and Cursor; HTTP replay did not duplicate jobs. |
| `go`: `hold`, then `go` | PASS | Hold created and cleared in saved session state. Follow-up answered `Ready when you are.` No extra job. |

The initial verifier measured HTTP/queue acceptance and finished before the asynchronous Claude failure. Follow-through changed the final evidence to `all_pass=false`; the original acceptance result is retained as `initial_acceptance_all_pass=true`. The deploy log's initial four PASS lines are not a release approval.

## Additional release blocker: old UI assets

The authenticated phone browser reached the public HTTPS site but timed out waiting for `/api/jobs/activity` after opening Jobs. No valid new-Jobs screenshot was produced. Both the local and public `/app.js` responses matched the old live data directory, not the clean candidate.

Root cause: `webchat/app.py` uses `HERE = Path(os.environ.get("BOB_WEBCHAT_DIR", ...))` for both persistent data and static files. The service launcher sets `BOB_WEBCHAT_DIR` to `conductor/webchat`. Pinning the Python code to the clean checkout therefore left the old UI in use. Source assets need their own code-relative path; password, sessions and locks must keep their existing data paths.

| app.js source | SHA-256 |
| --- | --- |
| local | `e9bdfe357a2987a24580f6ee0872d1e792882963a3fa7833db0a3ca12d1c2674` |
| public | `e9bdfe357a2987a24580f6ee0872d1e792882963a3fa7833db0a3ca12d1c2674` |
| candidate | `eba7c83e2a4318146243ed172dcc70ab0f04aacb45c1626d903982dc738d4c03` |
| live_data_directory | `e9bdfe357a2987a24580f6ee0872d1e792882963a3fa7833db0a3ca12d1c2674` |

## Original 15:22 failure

`going`, `claude161`, and `push2` failed with HTTP 401 Unauthorized. `hold` and `go` also returned 401, yet `go` was incorrectly marked true. Both earlier `e2e_live.py` invocations omitted required `--output`. The initial worktree creation failed because the MiniMax branch was already checked out; execution then fell back to dirty `conductor` at `6e3216d`. Thus the earlier green tests did not prove the intended deployment.

## Candidate and validation

Clean tip `7ab7f1311f70262932a9e8dcc7f78c096e996567` is included, along with MiniMax implementation `f2af459` and requested proof commit `855be8b5c9056e4f8d356b958cf6f136504d1ddb`. The candidate fixes the two missed exact phrases and adds session-cookie/CSRF authentication, durable job checks, replay checks and saved-hold checks. HTTP errors fail closed.

- 241 chat tests passed, including authentication failure, hold/go HTTP failure, exact status/push phrases and scoped hold persistence.
- 111 service tests passed, including MiniMax result acceptance.
- JavaScript test and syntax, bootstrap syntax and whitespace checks passed.
- All four checks passed in a private authenticated rehearsal with actual private queue writes and model calls forbidden.
- Isolated Jobs browser proof passed at 320/390/430/900 px, light/dark, including source-failure cases. The isolated proof did not reproduce the production data-directory override.

## Rollback and retained work

Rollback completed: 2026-09-27T21:09:33.008+00:00. Both deployment pins now point to `/Users/jeffstory/Documents/bob-overnight-inject/rollbacks/webchat-20260927-160618/deployed-code`. Webchat health was verified and job-runner reacquired its lifetime lock. Only webchat and job-runner were restarted for deployment and rollback; every unrelated screen identity stayed unchanged. Persistent queues, sessions and already launched project workers were retained.

| Job | Project/request | State observed after rollback | Worker |
| --- | --- | --- |
| `webchat-2fbdaf20f5a453a1a0af6c88fea5f0f9` | PR #161 | failed | gemini |
| `webchat-8a205eb9c55a5f9aad2c2cb6decaca5d` | WebJam | failed | codex |
| `webchat-848df09c919951d4a896392b0f2ccff2` | AdoptIQ | running | cursor |

Evidence: [live checks](WEBBOB-REDEPLOY-LIVE-0927.json), [deployment/rollback](WEBBOB-REDEPLOY-DEPLOYMENT-0927.json), [chat tests](WEBBOB-REDEPLOY-TESTS-0927.txt), [service tests](WEBBOB-REDEPLOY-SERVICES-0927.txt), [isolated rehearsal](WEBBOB-REDEPLOY-REHEARSAL-0927.json), [browser rehearsal](WEBBOB-REDEPLOY-BROWSER-0927.json).

The draft remains open. No merge, undraft, force-push, Grok/xAI call, or password disclosure occurred.

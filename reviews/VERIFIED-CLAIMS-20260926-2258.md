# Verified claims: Gemini + MiniMax reviews vs live code (22:58 CT)
Read-only check by the duplicate improve-rounds instance (claude pid 36563), which stood down because
`conductor/locks/improve-rounds.d` is owned by the sibling (ppid 36516) and `svc-harden` is rewriting services/.
For the lock owner and svc-harden: use this before applying the backlog.

## MiniMax review (LATEST-MINIMAX.md)
Not an architecture review. It restates log lines and asks "what would you like help with?". It has no ranked
fixes, so "fixes both agree on" reduces to the overlap of its log observations with Gemini's items. Re-run
`bin/minimax-arch-review.py` with a stricter prompt if a real second opinion is needed.
Overlaps with Gemini: WebJam worktree busy / fail-closed (Gemini #4, #6, #8) and Codex CLI failures (#6).

## Gemini top 10, checked against current code
| # | Verdict | Evidence / correction |
|---|---------|-----------------------|
| 1 stop self-mod | VALID, needs more than deleting PROMPT.md text | conductor_pass.py `run_agent` runs codex/claude with edit rights on ROOT, and its improvement stage exists solely to edit scripts. Need py_compile/bash -n gate + git rollback (harden item 2), not just prompt edits. |
| 2 rename BLOCKER.txt to ORPHAN_WARNING.txt | WRONG as written | jobs.py:56-61 writes BLOCKER on purpose so a cancelled legacy job is not relaunched. Under the new name `closeout()` returns None, so `recover()` (jobs.py:111-121) would write resume.sh and RELAUNCH the stale job. Fix is a `blocked` state in the journal (harden item 3), not a filename change. |
| 3 `< /dev/null` in run-conductor.sh | STALE | run-conductor.sh now execs conductor_pass.py, which already passes stdin=DEVNULL via process_control.run (timeout + killpg). |
| 4 cwd = folder | WRONG as written | A job folder is not a repo; the coder would run with no worktree. Real bug is worker.py:33 hardcoding `webjam-pr158-fold`. Fix: per-job `worktree`/`repo` field in the job record, or worktree derived from the queue row, with BLOCKER if missing. |
| 5 kill dueling orchestrators | VALID and live | `bash conductor/loop.sh` (pid 30668) was running beside the services. runtime.takeover() only retires a screen named `mini-conductor`; loop.sh here ran under a login shell, not that screen. Bob-Takeover.command still falls back to loop.sh when start-all.sh is not executable. Tombstone loop.sh (exit if services alive) rather than rm. |
| 6 force Claude for coding | UNVERIFIED | The evidence is the 2133 Codex sandbox not committing. Cleaner fix: Codex with a sandbox that can run git on draft branches only (harden item 6). Claude `-p --permission-mode acceptEdits` may also refuse `git commit`; test before switching engines. |
| 7 cap "$48" runaway | VALID, wrong fix | Editing Jeff's instruction to "2 passes" overrides his intent. Enforce the cap in code from API usage fields (harden item 7), not by LLM arithmetic. |
| 8 queue priority | PARTLY | tick.log shows `ci_unblock_pressure: true` and the refill guard was already patched for ci_unblock rows. Check `pick-next.py` ordering before renaming files. |
| 9 prepend hard rules | VALID, trivial | worker.py:23 appends rules after the job prompt. Prepend and keep the rules text in one immutable file. |
| 10 STATUS.md contention | VALID | PROMPT.md step 5 tells the LLM to overwrite STATUS.md while runtime.status_report() also atomic-writes it. Whichever runs last wins. Give LLMs `conductor/status/notes-<lane>.md`; runtime merges. |

## Live state seen at 22:54 CT
- `screen -ls`: only `webjam-identity-line-2238` and `svc-harden`. The four `svc-*` screens are absent although start-all.log
  says "started ... rc=0" then "screens missing after start". Probably svc-harden's staged shutdown (conductor/MAINTENANCE says
  "Hardening in progress: keep automatic scheduling paused"); confirm they come back when it finishes.
- Three `claude -p` instances with this same IMPROVE-ROUNDS prompt were queued (waiting on svc-build/svc-council/svc-gemini-review). Only one should run.
- BOB-HANDOFF.md is stale: it still says the automation is `screen -r mini-conductor` + `conductor/loop.sh`. Actual: four `svc-*`
  screens started by `conductor/services/start-all.sh`, ticks by job-runner (15 min), pass every 2 h via `svc-conductor-pass`.
  Its fix ("If the loop is gone: screen -dmS mini-conductor bash conductor/loop.sh") would recreate the dueling orchestrator.
- conductor/STATUS.md at 22:30 is from the LLM pass and will be overwritten by runtime.status_report() on the next pass.

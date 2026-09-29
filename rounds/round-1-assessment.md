# Round 1 assessment (2026-09-26 22:58 CT) — evidence-based

## Context
Gemini review (LATEST.md) top-10 and MiniMax review (LATEST-MINIMAX.md) exist. MiniMax's review contains NO ranked fixes: it
restated log errors (`--full-auto` unexpected arg in conductor.log; Cursor "Authentication required" in svc-webjam-ux.log;
worktree busy FAIL_CLOSED) and asked "what would you like me to help with?". So the only cross-agreement is on log symptoms:
codex CLI flag error, cursor auth, busy worktree.

## Live evidence (ps at 22:54)
- A `svc-harden` codex job (started 22:51) is ALREADY editing services/*.py to implement Gemini #2,#3,#4,#5,#6,#9,#10
  (git diff shows process_control.run_bounded w/ timeouts + stdin=DEVNULL + killpg in jobs/runtime/worker/conductor_pass).
  => I must not edit services/* concurrently; I verify after it finishes.
- 3 identical "Run 3 self-improvement rounds" claude sessions started within 20 s (pids 36390/36516/36563), all allowed to
  rewrite scorecard.md / STATUS.md.
- 2 identical "WebJam deep UI/UX pass" codex jobs (34413 @22:46, 36625 @22:53), both claiming to be the sole WebJam coder.
- Another codex "Build the 4 services" (32051, since 22:31) still alive after services exist.
  => nothing stops duplicate agents. No tool exists to answer "what agents are running and are any duplicates?".

## Gemini top-10, verified against the tree
| # | Claim | Verdict |
|---|-------|---------|
| 1 | delete self-improve mandate | Conflicts with Jeff's explicit standing mandates; keep but gate (py_compile + rollback; harden item 2). Flag to Jeff. |
| 2 | BLOCKER.txt on legacy import closes job | TRUE (jobs.py import_legacy + closeout). Owned by harden item 3. |
| 3 | stdin </dev/null | already true in conductor_pass.py (DEVNULL); harden adds killpg. run-conductor.sh now execs python. |
| 4 | hardcoded webjam-pr158-fold cwd | TRUE in worker.py. harden item 4. |
| 5 | dueling loop.sh vs runtime schedule_pass | TRUE; loop.sh still exists + Bob-Takeover.command falls back to it. |
| 6 | force claude for coding | Wrong fix: harden gives codex a commit-capable sandbox instead. |
| 7 | UX-MAX "EXACTLY 2 passes" | Contradicts Jeff's explicit $50 MiniMax authorization; real fix is script-enforced ledger (harden item 7). |
| 8 | rename row 20 -> 00 | Wrong: pick-next.py already has _CI_UNBLOCK preference + int pri; 17 was already RUNNING (screen alive) when 20 became READY. |
| 9 | prepend hard rules | TRUE (worker.py appends). Cheap; goes with harden. |
| 10 | STATUS.md single writer | TRUE (PROMPT.md tells LLM to overwrite; runtime.status_report also writes). harden item 8. |

## Broken / fragile / missing in MY lane (not owned by harden)
1. bin/ask-gemini.sh & bin/ask-minimax.sh: on total failure they print nothing and exit 0 (callers can't tell); prompt only via
   argv (ARG_MAX); Gemini call has no maxOutputTokens (INDEX.md rule 7 says truncation already bit us); MiniMax M2.7 can return
   <think> chain-of-thought inline; model is 2.5-flash while the review used 3.1-pro. These two scripts are the mechanism of every round.
2. BOB-HANDOFF.md is stale/wrong: describes loop.sh/mini-conductor as the automation, "council (once built)", 15-min cadence,
   no rule about concurrent agents, no MAINTENANCE-file semantics, no runbook (services down / tick FAIL_CLOSED / dirty worktree),
   no guidance on which model for which job, no skill index (51 skills in bob-brain with no table of contents).
3. ~/Desktop/Bob-Takeover.command: falls back to loop.sh (dueling orchestrator), ignores conductor/MAINTENANCE, doesn't show who
   is already running, doesn't sync/validate keys.
4. No `who-is-running` tool (see live evidence).

## Candidate fixes for round 1
A. Harden bin/ask-*.sh (nonzero exit on failure, stdin prompts, strip <think>, maxOutputTokens, model override env).
B. bin/who-is-running.sh: list agent processes, dedupe by prompt hash, flag duplicates/conflicting editors.
C. Rewrite BOB-HANDOFF.md + Takeover script + skill index.
D. Wait for harden, then verify Gemini #2/#4/#5/#9/#10 with tests.

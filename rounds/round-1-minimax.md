## Wrong/Unsupported Claims

1. **#3 "stdin </dev/null already true"** — Contradicted by own evidence: harden *adds* DEVNULL + killpg. If already true, harden wouldn't need it. Correct statement: DEVNULL *planned* but not verified implemented.
2. **#8 "Wrong fix"** — Claims pick-next.py's priority works, but live evidence shows 3 identical Claude sessions (36390/36516/36563) started within 20s, all allowed to rewrite same files. Priority logic is *not* preventing duplicates; the justification about "17 RUNNING" doesn't explain 3 concurrent identical jobs.
3. **#6 "Wrong fix"** — Calling Gemini's fix "wrong" without evidence codex would use the hardened sandbox is speculative. No test run demonstrates this.

## Missed

1. **Process group orphaned jobs**: "Build 4 services" (pid 32051) alive since 22:31 *after* services exist → zombie or hung job consuming resources.
2. **No git branch locking**: 3 agents rewriting STATUS.md/scorecard.md with no merge conflict handling; last-write-wins corrupts state.
3. **No watchdog for FAIL_CLOSED**: "worktree busy FAIL_CLOSED" appears in logs but no mechanism auto-recovers (kill stale processes, reset state).
4. **No model routing governance**: Which model for which job type is undefined; bin/ask-minimax.sh uses 2.5-flash vs review's 3.1-pro inference.
5. **No escalation protocol**: When agents detect conflicts, there's no protocol to defer vs. abort vs. notify.

## Fix Ranking

| Fix | Impact | Effort | Ratio |
|-----|--------|--------|-------|
| **A** | **High** — silent failures are root cause of unattended crashes; fixes prompt injection, output truncation, error masking | Low — shell script edits | **Best** |
| B | Medium — duplicates visible but not prevented | Medium — requires hash logic + cron integration | 2nd |
| C | Low-medium — documentation doesn't stop runtime failures | High — rewrite + validation | 3rd |
| D | Medium — tests good but doesn't fix broken mechanisms | Unknown — no test framework described | 4th |

## One Pick: **A**

`bin/ask-*.sh` hardening is the single highest-leverage change: it fixes silent failures (exit 0 on crash), truncates `<think>` output, enforces max tokens (prevents truncation damage), and enables proper error propagation to callers. All other reliability improvements (dedup, docs, tests) are moot if agents can't detect failures. Three lines of shell logic yields outsized reliability for unattended operation.

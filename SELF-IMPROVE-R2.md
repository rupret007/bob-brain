# Self-improvement round 2 (Cursor lane)
Measure first: read reviews/HARDEN-RESULT.md, HARDEN-EVIDENCE.md, WEBCHAT-RESULT.md, logs/ (watchdog, job-runner, reviewer, tick, webchat-launchd), STATUS.md.
Find the top 5 real holes by evidence (e.g. launchd exit 126 "Operation not permitted" auto-start, stale heartbeats, jobs that retried/blocked, lane idle time, spend tracking gaps). Rank by impact.
Implement the top 3 on a draft branch in a private worktree (core is read-only: go through the harden rollback/last-good path). Do not touch conductor/webchat/ (another job owns it). Add a regression test per fix; run all tests + shell syntax checks.
For the launchd 126: diagnose precisely (FDA scope, script location outside ~/Documents as a fallback wrapper, e.g. ~/bin launcher that cd's in) and fix if possible without Jeff; if Jeff must click something, say exactly what.
Never merge/undraft/force-push; no texts/emails; no spend beyond caps.
Write conductor/reviews/SELF-IMPROVE-R2-RESULT.md: holes ranked with evidence, what changed, PASS/FAIL, commit SHA, anything Jeff must do.

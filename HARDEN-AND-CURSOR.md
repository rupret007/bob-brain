# HARDEN + CURSOR LANE (Jeff: "implement all changes needed; make it actually work")
Read reviews/LATEST.md (Gemini) and reviews/LATEST-MINIMAX.md if present. Implement ALL top fixes in services/:
1. Single orchestrator: services/start-all.sh + watchdog own everything; loop.sh/mini-conductor becomes a thin shim that exits if services are running (pidfile lock).
2. Immutable core: PROMPT.md rules + services/*.{sh,py} are read-only to LLM jobs (chmod a-w, jobs work in git worktrees only). Before any self-edit takes effect: bash -n / python3 -m py_compile; on failure auto-rollback via git (keep conductor under git, tag last-good).
3. jobs.py: writing legacy BLOCKER.txt must NOT mark a job closed; blocked -> state=blocked, retried/escalated, never dropped.
4. worker.py: remove hardcoded ~/Documents/webjam-pr158-fold cwd; per-job repo/worktree from job spec.
5. Every CLI call: hard wall-clock timeout (python subprocess timeout or perl alarm; no coreutils timeout on this Mac), stdin </dev/null, kill process group on timeout.
6. Codex runs with sandbox that can commit/push (e.g. --dangerously-bypass-approvals-and-sandbox or workspace-write + network) — only on draft branches; never merge/undraft/force-push.
7. Spend tracked by script (ledger file per lane from API usage fields), hard stop MiniMax at $48; not by LLM.
8. STATUS.md written ONLY by runtime.py (LLMs write to status/notes-<lane>.md which runtime merges).
9. NEW CURSOR LANE (separate pool from Bob; use heavily): binary ~/.local/bin/cursor-agent. Headless: cursor-agent -p "<task>" --output-format text (check `cursor-agent --help` for force/model flags; use --force if needed for edits). Add as lane `cursor` in job runner, council (propose/critique), and reviewer. If `cursor-agent status` says Not logged in: lane state=needs_login, surface in STATUS.md, do not crash; auto-activate when logged in (check each tick).
10. Lane scheduler: 5 lanes (codex, claude, cursor, gemini, minimax), up to 5 concurrent, max one WebJam coder at a time, no shared worktree. Idle lanes pull from backlog (project priority WebJam > StoryBoard > AdoptIQ > shelf: #159/#160 test_art_host_platforms red, AdoptIQ #26 rebase onto #25, keep SB #47 + shelf #10 green, UX PUNCHLIST items).
11. Update BOB-HANDOFF.md "All AI resources" with cursor lane.
Rules: drafts only, never merge/undraft/force-push, no texts/emails, no Cursor Cloud agents.
Verify: run a smoke test of each lane (short prompt), bash -n everything, start-all.sh up, write results to reviews/HARDEN-RESULT.md with pass/fail per item. Commit conductor changes to git.

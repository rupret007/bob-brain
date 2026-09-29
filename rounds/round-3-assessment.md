# Round 3 assessment (23:15 CT): the takeover stand-in
A fresh Claude/Codex session double-clicked from ~/Desktop/Bob-Takeover.command must act as Bob using only BOB-HANDOFF.md + bob-brain/.
Evidence of defects (verified against the tree):
1. BOB-HANDOFF.md points at `inbox/` (does not exist; real path next-prompts/_inbox/); describes `screen -r mini-conductor` + loop.sh as the automation
   (harden retired it; the real automation is four svc-* screens + start-all.sh); says council is "once built" (built: conductor/services/council.sh);
   "Open items" are a frozen snapshot (Sep 26 10:25 PM) presented as current; no mention of conductor/MAINTENANCE (pauses scheduling) or alerts.json.
2. No runbook for the 3 failures actually seen in logs: tick FAIL_CLOSED "webjam worktree busy" (dirty tracked file in the sole WT), services DOWN,
   `codex exec` flag errors / CLI hangs.
3. Rules are one bullet list. bob-brain memory holds more rules that a stand-in never sees: never store/reuse API keys pasted in chat; fail closed rather than fake PASS;
   CI green before calling anything ready; Jeff owns feel/set-list/merge; older memory ("Bob may move PRs forward when green") is SUPERSEDED by "never merge".
4. Resource use undefined: which model for which job (Codex=coding in worktrees, Claude=review/research/long reading, MiniMax=bulk UX/review passes with $ credit,
   Gemini=long-context/second opinion, Cursor lane=needs login), when to use council, how to avoid duplicate agents (bin/who-is-running.sh --check now exists).
5. bob-brain has 49 skills and no index -> a stand-in either reads none or reads all 179 KB. A generated one-line-per-skill index is needed.
6. Bob-Takeover.command: elif fallback to loop.sh (the dueling orchestrator Gemini flagged), ignores MAINTENANCE, doesn't show who is already running
   (duplicate agents exist right now), doesn't check claude/gh auth, `git pull` on bob-brain silently swallowed.
7. Nothing keeps the handoff honest: a doc that names 15 paths and 8 commands drifted within hours.
Proposed C: (a) rewrite BOB-HANDOFF.md: RULES / FIRST 2 MINUTES / RUNBOOK / RESOURCES (routing table) / HOW-TOs / where things live; generated open items are NOT hand-typed
(point at STATUS.md), (b) bin/build-skill-index.py -> BOB-SKILL-INDEX.md, (c) Takeover script: no loop.sh fallback, honors MAINTENANCE, runs who-is-running + auth checks first,
(d) bin/check-handoff.py verifies every backticked path/command in BOB-HANDOFF.md exists (drift test).

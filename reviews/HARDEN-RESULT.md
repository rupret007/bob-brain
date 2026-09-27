# HARDEN + CURSOR result

Verified 2026-09-27T04:28:28+00:00 (Mini only). Implementation commit: `8b2f9c1` on
`draft/harden-cursor`. The local `last-good` tag identifies the checked core.
All 11 implementation items PASS. All five live lane smoke tests PASS.
47 regression tests PASS; 15 maintained shell syntax checks PASS;
Python compile checks PASS. Four service screens are running with fresh heartbeats.

| Item | Result | Evidence / resulting behavior |
| --- | --- | --- |
| 1. One orchestrator | PASS | start-all/watchdog own the four services. Lifetime flock + PID files prevent duplicates; repeat startup retained the same PIDs. loop.sh exits while services own the lock. Old queue launchers delegate to that same authority. Retired legacy loop/build/improve/council/UX parent shells and their surviving descendants. |
| 2. Immutable core and rollback | PASS | PROMPT.md, bootstrap and services are chmod a-w. The macOS job boundary rejects same-user writes to the live core. All CLI work runs in private Git worktrees. Bootstrap compiles Python and checks Bash before importing; an injected syntax error in a disposable Git repository was quarantined and restored from last-good. Scheduled assessments never apply changes. |
| 3. Blockers remain unfinished | PASS | BLOCKER.txt never closes a job. Prior misclassified legacy blockers are reopened as blocked. Managed jobs back off/retry and escalate after three attempts. Result verification, idempotent harvest and a late BLOCKER invalidation are tested. |
| 4. Per-job worktrees | PASS | Every managed job records repo, worktree and draft branch. The shared hardcoded worker cwd is removed. Two real test worktrees remained separate; live jobs also use separate paths under ../workspaces/. |
| 5. CLI hard limits | PASS | command.run closes stdin, starts a process group and kills descendants on timeout/signals. A real TERM-resistant grandchild was killed. Screen launchers alone may detach after a successful bounded launch. curl has connect/request limits; credentials use private config files. |
| 6. Commit/push-capable Codex | PASS | Coding uses the verified bypass flag inside the separate core write boundary. A real local commit and normal push passed inside that boundary. Hooks deny main/release/other targets and non-fast-forward pushes. Existing PRs must be open drafts. Rebased replacements have an explicit new draft target and must produce an open draft PR. |
| 7. Script-owned spending | PASS | Per-lane ledgers record usage; reservation and settlement are fsynced and locked. Concurrent reservations and cap refusal are tested. MiniMax requests that could exceed $48 are rejected before transport. Prior UX calls were imported once; uncertain calls retain reservations. All active ask/tip/architecture/UX helper paths use the metered transport. |
| 8. STATUS ownership | PASS | runtime.py is the only STATUS writer. state.alert updates JSON only. Workers copy worktree STATUS-NOTE.md into status/notes-<lane>.md; runtime merges it. |
| 9. Cursor lane | PASS | Cursor is logged in and passed the real prompt. --trust is used; --force enables coding. Cursor participates in scheduler, council proposals/critiques/synthesis and reviewer, using the separate local pool. Tests cover needs_login and automatic activation on the next tick. |
| 10. Five-lane scheduling | PASS | Shared leases cover codex/claude/cursor/gemini/minimax across jobs/council/reviews. Up to five managed jobs; one WebJam coder; no shared worktrees. Backlog prioritizes WebJam CI, UX punchlist, StoryBoard #47, AdoptIQ #26/#25, then shelf #10. A separate active WebJam test-build claim is honored; scheduler-owned WebJam work waits and preserves its worktree. |
| 11. Handoff | PASS | ../BOB-HANDOFF.md now documents all five AI resources, Cursor usage, the scheduler, worker isolation, the ledger, and runtime status ownership. A committed copy is docs/BOB-HANDOFF.md; compat contains installed legacy wrappers. |

| Required live verification | Result |
| --- | --- |
| Codex / Claude / Cursor / Gemini / MiniMax short prompt | PASS / PASS / PASS / PASS / PASS — reviews/SMOKE.md |
| Regression tests | PASS — 47 tests, including actual process death, Git rollback, commit/push boundary, billing races and final-response parsing |
| bash -n | PASS — 15 maintained shells; no GNU timeout dependency |
| Python compile gate | PASS |
| start-all.sh | PASS — exit 0, all four screens and lifetime locks verified |
| Repeat start-all and legacy shim | PASS — unchanged service PIDs; shim exits 0 |
| launchd/install.sh | PASS — bob-services and bob-watchdog installed and loaded; old timers retired |
| Git checkpoint | PASS — implementation committed locally and last-good tagged; no remote push required |

MiniMax at verification: **$1.081031 recorded +
$1.154044 reserved = $2.235075 / $48**.
Subscription CLI token/cost fields are recorded when provided; unavailable dollar
charges remain unknown. The cap covers the configured conductor transport, not
unrelated API clients using the same account.

The first smoke prompt was shorter than the API answer validator accepted. It was
corrected and all five were rerun successfully; rejected responses were still metered.
Live validation also caught progress text hiding a final BLOCKER. The parser now
uses the last final message, and misclassified managed closeouts were reopened.
A prepared AdoptIQ rebase needed a new draft target; that path is now authorized
in its job specification and verified without allowing a force-push.

**23:07 CT Claude update: PASS.** Codex and Cursor own coding/orchestration. Claude is restricted to short council critiques and small reviews (one call, at most 6,000 context characters and 120 seconds), with a durable one-hour rate-limit cooldown. It neither proposes nor synthesizes council plans. Tests verify routing, prompt limits and cooldown refusal. Takeover already prefers Codex.

Project work is ongoing, separate from these infrastructure PASS results. Old
blocked jobs remain visible. The WebJam test build has an external coding claim;
other project lanes continue. These results do not claim every project CI check
is green or that Jeff's feel/Final Build checks are complete. LaunchAgents run at
user login; auto-login/account settings were intentionally not changed. The newer
review's auto-login/PAT suggestions were addressed with login-time LaunchAgents
and bounded credential calls, respecting the no-login-change rule.

Concurrent webchat/test-build work and its files were preserved. Their separate
in-progress edits are not represented as hardening changes. No PR merge, undraft,
force-push, text, email, purchase or Cursor Cloud agent was performed by this task.

Exact service PIDs, heartbeats, smoke durations and checks are in
[HARDEN-EVIDENCE.md](HARDEN-EVIDENCE.md). Runtime state remains in STATUS.md,
jobs.jsonl, alerts.json, ledger/, and ../logs/.

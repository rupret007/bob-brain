# Multi-LLM same-project swarm architecture (v1, 2026-09-27)
Goal: many LLMs on ONE project at once, minimal wall-clock time, no merge hell.

1. Contract-first split: Architect (Codex/Claude) writes interfaces + tests first (module boundaries, function signatures, API shapes) and commits them to an integration branch. Workers code against frozen contracts.
2. File-ownership leases: every task claims a set of paths (lease file in conductor/leases/<project>.json). Planner never assigns overlapping paths concurrently; shared hot files (router, reply builder) get split into modules first (a refactor task that runs alone, early).
3. Integration train: one integration branch per project. A merge-bot rebases each finished worker branch onto the train tip every few minutes, runs tests + eval suite; green = fast-forward the train; red = bounce back to the same worker with the failure. Small, frequent merges beat big late merges.
4. Conflict resolver role: when a rebase conflicts, a dedicated resolver (Codex) gets both diffs + intent and resolves, then tests. Workers never resolve each other's conflicts.
5. Roles by strength:
   - Codex: architecture, hard multi-file fixes, conflict resolution, deploys.
   - Claude: long-context design, reply/UX quality, careful refactors, final review.
   - Cursor (local, plentiful): parallel feature implementation inside a lease, test writing.
   - Gemini: big-context audits (whole repo), gap analysis, planning, second review.
   - MiniMax: cheap high-volume reviews, test-case generation, eval grading, critique on every push.
   - Never Grok/xAI.
   Avoid weaknesses: cheap models never deploy or resolve conflicts; no model reviews its own code; high-cost models only on hard/critical paths.
6. Gates: every merge to train = tests + eval suite + cross-model review (different vendor than author). Deploy = train tip only, rollback point, live checks.
7. Honest board: one state file per project listing each worker, LLM, lease, task, branch, SHA, status; Web Bob reads this for "what's working on what".
8. Rollout: build planner + leases + merge-train in conductor as services, prove on Web Bob, then apply to WebJam/AdoptIQ/StoryBoard/Fantasy.

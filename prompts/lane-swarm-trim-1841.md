You are Codex on Jeff's Mac Mini. Work ONLY in:
  ~/Documents/bob-overnight-inject/workspaces/swarm-arch-1730
Branch: draft/swarm-arch-1730 (currently c027334). Drafts only — never merge/undraft/force-push. No deploy. Never print secrets.

GOAL: Trim the swarm-arch draft per research — reuse existing tools; only keep novel gaps.

Read:
- ~/Documents/bob-overnight-inject/conductor/reviews/SWARM-RESEARCH-0927.md (esp. exec summary, §8 novelty, §9 ranked changes, §10 v2)
- docs/MULTI-LLM-SWARM-ARCH-0927.md, docs/SWARM-V1.md
- Current swarm implementation commits on this branch

Actions:
1. Inventory what draft/swarm-arch-1730 added (leases, merge train, board, etc.).
2. DELETE or gut code that merely reimplements prior art already covered by Git worktrees, GitHub/GitLab merge queues, Cursor worktrees/Projects, existing conductor job runner / screens / reviewers.
3. KEEP only novel/P0 project-specific gaps: enforceable vendor-neutral integration policy, transactional/fenced leases with recovery, exact-candidate train evidence binding, versioned task contracts + acceptance checks — as thin modules, not a full framework rewrite.
4. Update docs to say "reuse X; we only own Y" with pointers to SWARM-RESEARCH-0927.md.
5. Run any existing tests; don't break webchat.
6. Commit + push draft/swarm-arch-1730 (no force).
7. Write ~/Documents/bob-overnight-inject/conductor/reviews/SWARM-TRIM-1841.md summarizing removed vs kept, tip SHA.

No Jeff notify.

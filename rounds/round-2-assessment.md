# Round 2 assessment (23:03 CT)
Round 1 shipped (bin/llm_ask.py; ask-*.sh now fail loudly). Evidence still open at 23:03:
- Two identical `codex exec "WebJam deep UI/UX pass, MAX effort..."` processes (pid 34413 started 22:46 on ttys014, pid 36625 22:53 on ttys009),
  each told it is the sole WebJam coder. One-coder rule is only enforced by screen-name regex in pick-next.py; ad-hoc terminal launches bypass it.
- `ps` lists 3 process layers per agent (login -> bash -lc "<full prompt>" -> codex); naive dedupe by command text triple-counts.
- Stale/hung suspicion: `codex exec "Build the 4 independent services..."` pid 32051 alive 25 min after the services exist.
- Nobody (incl. the takeover stand-in) has a single command answering "what agents are running, are any duplicates/conflicting, which are stale?".

Proposed fix B: `bin/who-is-running.py` (+ .sh wrapper), READ-ONLY, bash3.2/py3 stdlib only:
 * enumerate real agent processes = executable basename in {claude, codex, cursor-agent} (skip login/bash wrappers, skip *.app helpers, skip the
   interactive no-arg `claude`), plus `screen -ls` sessions and services heartbeats age.
 * per process: pid, ppid chain tty, elapsed, cwd (lsof), normalized-prompt hash (first 300 chars after flags), first-line label.
 * flags: DUP (same hash >1 pid), CODER-CONFLICT (>1 coder whose prompt/cwd mentions same repo e.g. webjam), STALE (> N hours, default 3), SELF (caller's own ancestor).
 * `--check "<prompt or @file>"` exits 1 if an equivalent agent is already running => launchers/Bob call it before spawning. `--json` for tooling.
 * never kills anything (reports the exact `kill <pid>` a human would run). Exit 0 clean, 1 dup/conflict found.
Risks I see: prompt normalization false positives/negatives; lsof cwd cost; a "coder" heuristic based on prompt text is fuzzy.

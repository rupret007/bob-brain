## Critique

### Fragile Design Points

1. **Prompt normalization is too naive** — First-300-char hash collides on semantically different prompts and misses context buried later. "webjam" detection via string search is brittle (case, path variants, substrings in unrelated contexts).

2. **TTY-based deduplication fails** — Same agent relaunched on a different `tty` won't be caught as duplicate if prompt hashes differ slightly. TTY is a session proxy, not an identity.

3. **`screen -ls` assumes screen** — macOS users often use iTerm2 windows, tmux, or no session manager. Misses most real deployments.

4. **`lsof` for cwd is expensive and unreliable** — Can hang on NFS, requires permissions, and cwd may be inaccessible for zombie-ish processes (your pid 32051 suspicion).

5. **Executable heuristics miss wrappers** — Many codex/claude invocations go through shell wrappers, aliases, or LaunchAgents. The basename check excludes real work spawning as child processes.

### Concrete Fixes

- **Heartbeat files**: Have agent launchers write `$AGENT_STATE_DIR/<pid>` with metadata (prompt-hash, start-time, repo). Eliminates ps/lsof dependency entirely.
- **Repo detection**: Use `git -C "$cwd" remote get-url origin` instead of prompt string matching.
- **Process enumeration**: Use `pgrep -P <ppid> -a` to walk process trees cleanly; skip walking into `launchd`, `login`, `Terminal`.
- **STALE**: Define as *no heartbeat update* for N minutes, not wall-clock time.
- **`--check` semantics**: Be precise — exit 1 only on **exact** prompt-hash match (not fuzzy repo conflict), and only within a short time window (e.g., <10 min) to avoid false positives from re-runs.

### Scope: READ-ONLY vs Auto-Kill

**READ-ONLY + `--check` is correct initial scope.** Auto-kill requires restart policies, signal semantics (SIGTERM vs SIGKILL), and rollback safety. The `--check` gate is the right integration point for launchers. If an operator wants auto-kill, that should be a separate daemon with explicit config, not part of a reporter.

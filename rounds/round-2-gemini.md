This Round-2 plan is a good step towards critical visibility.

1.  **Fragile Design:**
    *   **Prompt Normalization:** "First 300 chars after flags" is too simplistic. Different flags, whitespace, or minor wording changes can cause false negatives (same job, different hash) or false positives (different jobs, similar prefix). The "coder" heuristic by fuzzy prompt/cwd text is also prone to error.
    *   **`lsof` for CWD:** `lsof` can be slow, resource-intensive, and may require elevated privileges.
    *   **Stale Detection:** A fixed "N hours" is arbitrary; some agents legitimately run longer.
    *   **`screen -ls`/heartbeats:** Unclear how these relate to `codex`/`claude` agent processes, potentially diluting the focus.

2.  **Fixes/Edge Cases:**
    *   **`ps` Quirks:** Use `ps auxww` for full (untruncated) command lines and `ps -o cwd` (macOS specific) for efficient CWD retrieval, avoiding `lsof`.
    *   **Normalization:**
        *   Implement stricter normalization (case-folding, boilerplate removal).
        *   **Concrete Fix:** For reliable deduplication, *mandate* a `--job-id <UUID>` or `--project <name>` flag on `llm_ask.py` that agents pass through. This provides a stable, explicit identifier, eliminating fuzzy prompt parsing.
    *   **Stale:** Make `N` configurable per agent/project. Consider checking for recent file/TTY activity for a more robust "liveness" signal.
    *   **False Positives:** Ensure `--check` robustly excludes `who-is-running.py` and its parent processes (`SELF` flag helps).

3.  **READ-ONLY vs. Auto-kill:**
    *   **READ-ONLY is absolutely the right initial scope.** Auto-killing carries high risk (data loss, interrupted legitimate work) and should only be considered for highly confident, low-risk scenarios after extensive testing and with explicit opt-in. Reporting `kill <pid>` empowers humans to make informed decisions without introducing automation hazards.

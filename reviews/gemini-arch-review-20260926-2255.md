# Gemini architecture review (gemini-3.1-pro-preview) 20260926-2255

Here is the rigorous, blunt architectural assessment of the Mini conductor system.

### 1. Verdict
**Probability of surviving 5 unattended days: 0%.** 
The system is already actively failing, eating its own tail, and deadlocking. The logs show that runaway AI self-modification has already injected a Python syntax error (`x", "claude"):` in `svc-build.log`), the job queue is permanently blocked by a hardcoded folder path (`FAIL_CLOSED` in `tick.log`), and a race condition in the service launcher is crashing the watchdog (`cycle error: screens missing` in `start-all.log`). If the Mac mini reboots, the system will never start because `LaunchAgents` require a GUI login.

### 2. Architecture Critique
*   **Single Points of Failure (SPOFs)**: 
    *   **The Mac Mini Login Window**: `LaunchAgents` do not execute until Jeff logs in. An unattended reboot (e.g., macOS auto-update or power flicker) will hang at the login screen forever.
    *   **`webjam-pr158-fold`**: Hardcoded in `worker.py`. All coding stops if PR #158 is dirty.
*   **Failure Modes**:
    *   **Runaway Self-Modification**: The two-hour pass uses `conductor_pass.py` to give Claude/Codex root-level write access to the orchestrator scripts. An LLM hallucination will (and already did) corrupt the orchestration Python files.
    *   **CLI Auth Expiry / Keychain Lock**: `runtime.py` calls `gh auth token` to push dashboard updates. If the machine reboots, the macOS keychain is locked. `gh` will block indefinitely waiting for a password prompt, hanging the `dashboard-updater` forever.
    *   **Hung Processes**: `subprocess.run` calls to `claude` and `codex` use timeouts up to 5400s (1.5 hours). If they hang on a TTY prompt, they tie up the lane and memory.
    *   **Concurrent Screen Battles**: `takeover()` attempts to kill `mini-conductor`. If it fails (e.g., PID lock edge cases), you will have the legacy `loop.sh` and the new `job-runner.sh` both fighting to launch ticks, triggering race conditions in `jobs.jsonl`.
    *   **Log Growth**: Unbounded `>>` appends in `start-all.sh` and `common.sh`. Over 5 days, runaway error loops will generate gigabytes of logs, potentially starving the 256GB Mac mini SSD.

### 3. Logic Flaws and Contradictions
*   **Contradiction: Hardcoded CWD vs Queue Intent.** 
    *   *Evidence*: `worker.py` line 34: `cwd = Path.home() / "Documents/webjam-pr158-fold" if coding and "webjam" in job else folder`
    *   *Flaw*: The AI is instructed to work on PRs #159 and #160 (`PROMPT.md`), but `worker.py` dynamically overrides the directory to force *all* WebJam jobs into `webjam-pr158-fold`. The queue is deadlocked because this folder is dirty.
*   **Contradiction: STATUS.md Ownership.** 
    *   *Evidence*: `PROMPT.md` line 12 tells the AI: "Overwrite conductor/STATUS.md (under 15 lines)". But `runtime.py` line 230 (`status_report`) does: `atomic_write(CONDUCTOR / "STATUS.md", "\n".join(lines + grouped) + "\n")`.
    *   *Flaw*: The AI and the Python runtime both blindly overwrite `STATUS.md`. The Python script wipes out the AI's 15-line prose every cycle. 
*   **Flaw: The Watchdog Suicide.** 
    *   *Evidence*: `runtime.py` line 256 (`cycle("watchdog")`) calls `takeover()`. `takeover()` checks for screens (line 88) and raises `RuntimeError("screens missing")` if they aren't up. 
    *   *Flaw*: If any screen drops, the watchdog raises an exception. `cycle()` catches it and exits 1, *meaning the watchdog never updates its own heartbeat*. The watchdog essentially kills itself if it sees a sick peer.
*   **Flaw: Instant Race Condition in `start-all.sh`.**
    *   *Evidence*: `runtime.py` line 276. `ensure_services()` runs `screen -dmS`. Then `time.sleep(1)`. Then `takeover()` checks `screen -ls`.
    *   *Flaw*: `screen` initialization often takes >1 second. `takeover()` fails to find the sockets, crashes with `RuntimeError`, and aborts the startup.

### 4. Safety: Erosion of Hard Rules
**Can self-improvement erode the hard rules? Yes.** 
In `conductor_pass.py` line 96, the system gives the AI this prompt: *"Apply exactly ONE small safe learned improvement"*. It then executes it with `run_agent()`, granting full workspace write access (`--permission-mode acceptEdits`). The AI can trivially rewrite `PROMPT.md`, `worker.py`, or `council.py` to remove the string `"never spend money"` or alter the API keys. 

**Proposed Guardrails**:
1.  **Read-Only System Sandbox**: Isolate orchestration scripts from job worktrees. Do not give the two-hour pass `acceptEdits` permission on `/bin` or `/conductor`.
2.  **Diff Review / Quorum**: Change `conductor_pass.py` to output a `.patch` file instead of directly applying. Have the multi-model `council.py` review the `.patch`. Only apply via `patch -p1` if 3 out of 4 models vote `SAFE`.
3.  **Immutable Rules File**: Move the "Hard Rules" out of `PROMPT.md` into a `HARD_RULES.txt` file with read-only OS permissions (`chmod 444`). Prepend this file to *every* prompt automatically at the Python execution layer, so the AI cannot bypass it by rewriting prompts.

### 5. Ranked Top 10 Concrete Fixes (Impact vs Effort)

**1. Stop Runaway AI Self-Modification (Critical Safety)**
*Change*: Disable write-access for the learning pass so it doesn't break Python files.
*File*: `conductor/services/conductor_pass.py` Line 102 (inside `improvement_prompt` execution).
*Fix*: 
```python
# Change run_agent to use a read-only sandbox or just log the improvement.
# Replace apply_ok = run_agent(...) with:
apply_ok = run_agent(improvement_prompt + " Output a .patch file only. Do not apply.", folder / "improvement.log")
```

**2. Remove Hardcoded PR Folder (Unblocks Queue)**
*Change*: Let the WebJam jobs run in their assigned `folder`.
*File*: `conductor/services/worker.py` Line 34.
*Fix*:
```python
# Remove: cwd = Path.home() / "Documents/webjam-pr158-fold" if coding and "webjam" in job else folder
# Replace with:
cwd = folder
```

**3. Fix Watchdog Suicide via Takeover Exception (Stabilizes Services)**
*Change*: Catch the takeover exception so the watchdog loop can finish its heartbeat.
*File*: `conductor/services/runtime.py` Line 256.
*Fix*:
```python
# Replace takeover() with:
try:
    takeover()
except Exception as e:
    log("takeover deferred: " + str(e))
```

**4. Fix Screen Race Condition on Startup (Stops Crash Loop)**
*Change*: Add a polling wait in `takeover()` instead of an instant check.
*File*: `conductor/services/runtime.py` Line 84.
*Fix*:
```python
# Replace immediate screen session check with:
for _ in range(10):
    sessions = screen_sessions()
    if all("svc-" + name in sessions for name in INTERVALS):
        break
    time.sleep(1)
else:
    log("takeover pending: waiting for all four service screens")
    return
```

**5. Prevent Reboot Lockout (Ops Fix)**
*Change*: LaunchAgents don't run until login.
*Fix*: (No code change). Go to Mac `System Settings -> Users & Groups`, and set **Automatically log in as Jeff**. 

**6. Bypass GitHub CLI Keychain Hang**
*Change*: Prevent `gh` from triggering a blocking GUI password prompt.
*File*: `conductor/keys.env`
*Fix*:
```bash
# Add your GitHub Classic PAT to keys.env so the system bypasses `gh auth`
BOB_DASHBOARD_TOKEN="ghp_your_actual_token_here"
```

**7. Stop STATUS.md Clobbering**
*Change*: Python writes to telemetry, AI writes to STATUS.
*File*: `conductor/services/runtime.py` Line 230.
*Fix*:
```python
# Replace: atomic_write(CONDUCTOR / "STATUS.md", "\n".join(lines + grouped) + "\n")
# With:
atomic_write(CONDUCTOR / "telemetry.md", "\n".join(lines + grouped) + "\n")
```
*(Also tell the AI in `PROMPT.md` to read `telemetry.md` before overwriting `STATUS.md`)*.

**8. Isolate Worker Exits from Legacy Blockers**
*Change*: `jobs.py` creates `BLOCKER.txt` for legacy jobs, but `worker.py` aborts if it exists.
*File*: `conductor/services/worker.py` Line 18.
*Fix*:
```python
# Replace the abort condition to ignore legacy blocker texts
if (folder / "RESULT.txt").exists() or (folder / "RESULT.md").exists():
    return 0
```

**9. Fix `keys.env` Export in Subprocesses**
*Change*: `worker.py` and `conductor_pass.py` strip `env` variables, potentially losing `keys.env` for CLI agents.
*File*: `conductor/services/worker.py` Line 40.
*Fix*:
```python
# After env = dict(os.environ), ensure API keys are populated directly from the file:
if (CONDUCTOR / "keys.env").exists():
    for line in (CONDUCTOR / "keys.env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
```

**10. Add File Size Limits to Log Growth**
*Change*: Prevent unbounded disk fill in the bash wrapper.
*File*: `conductor/services/common.sh` Line 12.
*Fix*:
```bash
# Before exec >> "$BOB_ROOT/logs/$name.log"
if [ -f "$BOB_ROOT/logs/$name.log" ]; then
    tail -n 5000 "$BOB_ROOT/logs/$name.log" > "$BOB_ROOT/logs/$name.log.tmp" && mv "$BOB_ROOT/logs/$name.log.tmp" "$BOB_ROOT/logs/$name.log"
fi
```

### 6. Simplest Robust Target Design

The reliance on `screen` for daemons is deeply flawed. `screen` is for interactive TTYs, not daemon supervision. The architecture should be flattened to a single Python Supervisor daemon that spawns background processes natively.

```text
+-------------------------------------------------------------------+
|  macOS System (Auto-Login Enabled)                                |
|  +-------------------------------------------------------------+  |
|  | LaunchDaemon / LaunchAgent (com.jeff.bob-supervisor)        |  |
|  | Executes: `python3 supervisor.py`                           |  |
|  +------------------------------+------------------------------+  |
|                                 |                                 |
+---------------------------------v---------------------------------+
|                    Python Supervisor (PID 1)                      |
|                                                                   |
|  [ Thread 1: Tick Runner ]   [ Thread 2: Dashboard ]              |
|  Every 15m:                  Every 5m:                            |
|  - Run ops-queue-refill      - Push JSON via requests/urllib      |
|                                                                   |
|  [ Thread 3: Reviewer ]      [ Thread 4: Pass Scheduler ]         |
|  Every 5m:                   Every 2h:                            |
|  - Call Gemini/MiniMax       - Spawn read-only AI council         |
|                                                                   |
+--+--------------------------+-------------------------+-----------+
   |                          |                         |
+--v---------+       +--------v---------+      +--------v---------+
| Worker Job |       | Worker Job       |      | Worker Job       |
| (WebJam)   |       | (StoryBoard)     |      | (AdoptIQ)        |
| subprocess |       | subprocess       |      | subprocess       |
+------------+       +------------------+      +------------------+
```
**Why this is robust:**
1. **No Screen/Sockets:** You eliminate IPC timing bugs, `screen -ls` parsing regex errors, and dead sockets.
2. **Native Threading:** Threads share the same memory space for metrics (no fsync locked JSON files needed just to share "healthy" status).
3. **Graceful Failure:** If a worker dies, Python's `subprocess.Popen` catches the exit code immediately. No need to tail logs or guess if `screen` crashed. 
4. **Read-Only Codebase:** AI agents run against the worktrees, but the orchestrator scripts run under a different OS context (or file permissions) and physically cannot modify the Python supervisor.
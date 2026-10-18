# Gemini architecture review (gemini-3.1-pro-preview) 20260926-2248

Here is the rigorous architectural assessment of the autonomous multi-LLM work system.

### 1. Verdict
**Will it survive 5 unattended days?** **NO. Probability: < 1%.**
**Why:** The system is engineered to mutate its own orchestrator while you are away. `PROMPT.md` and `IMPROVE-ROUNDS.md` mandate continuous self-modification of system scripts (`bin/`, `services/`). Large Language Models inevitably hallucinate bash quotes, Python indentations, or logic boundaries. Within 48 hours, a "self-improvement" pass will introduce a syntax error into `runtime.py`, `jobs.py`, or `worker.py`, crashing the tick loops. Furthermore, competing orchestrators (`loop.sh` vs. `watchdog.sh`) are creating race conditions, and critical WebJam coding jobs are already failing due to unhandled CWD hardcoding and CLI sandbox restrictions.

### 2. Architecture Critique
*   **Single Points of Failure (SPOFs):** 
    *   **The Orchestrator Sandbox:** `STATUS.md` explicitly notes the "Codex 2133 sandbox couldn't commit/push", yet `WEBJAM-UX-MAX.md` and `worker.py` rely entirely on this CLI for WebJam tasks. WebJam coding is permanently bottlenecked.
    *   **Hardcoded Worktrees:** `worker.py` (Line 25) hardcodes `cwd = Path.home() / "Documents/webjam-pr158-fold"` for all WebJam jobs. If a job targets PR #160 (which is in a different fold/branch), it will either fail or silently corrupt PR #158.
*   **Failure Modes:**
    *   **Runaway Self-Modification:** AI alters `common.sh` or `jobs.py`, breaking the queue and causing total failure.
    *   **Hung Processes:** `run-conductor.sh` invokes `codex exec` and `claude` without redirecting `stdin`. If either CLI pauses for an interactive prompt (e.g., Anthropic's `acceptEdits`), the 2-hour loop will hang indefinitely, permanently freezing the orchestrator.
    *   **Cost Runaway:** `WEBJAM-UX-MAX.md` commands MiniMax to do "MANY passes" and "stop at about $48" by tracking token math in `spend.log`. LLMs cannot reliably do math across context windows; it will loop until your API account is drained.
    *   **Concurrent Overwrites:** `PROMPT.md` tells the LLM to "Overwrite conductor/STATUS.md". Simultaneously, `runtime.py`'s `status_report()` function uses `atomic_write` on the same file. The LLM's raw `>` bash redirect will inevitably truncate or clobber Python's system metrics.
*   **State Durability:** The `state.py` primitives (`atomic_write`, line-delimited JSON journals) are actually excellent and robust against power-loss/reboots. However, `jobs.py` abuses this by writing a `BLOCKER.txt` for unresolved legacy states, triggering a fatal logic flaw (see Section 3).
*   **Observability:** Scattered and fragmented. A `watchdog.sh` restart simply logs "restarted". If `worker.py` dies from an LLM-induced syntax error, the orchestrator has no telemetry to page you—it will just fail-close the loop.

### 3. Logic Flaws & Contradictions
*   **Flaw: Legacy Import Dropping Jobs (`conductor/services/jobs.py` lines 43-46)**
    *   *Evidence:* `atomic_write(folder / "BLOCKER.txt", "BLOCKER: legacy running record has no live screen...")`
    *   *Why it fails:* `jobs.py` line 22 identifies any job with a `BLOCKER.txt` as complete (`closeout`). By writing `BLOCKER.txt` to warn about a missing legacy job, the system immediately harvests it as "done" and permanently drops the work.
*   **Flaw: Dueling Orchestrators (`conductor/loop.sh` vs `conductor/services/runtime.py`)**
    *   *Evidence:* `loop.sh` line 7 triggers `run-conductor.sh` every 2 hours. `runtime.py` line 89 (`schedule_pass()`) *also* triggers `run-conductor.sh` every 2 hours.
    *   *Why it fails:* They will spawn simultaneous screen sessions that overwrite each other's logs and API calls. 
*   **Flaw: Priority Inversion (`logs/tick.log` vs `conductor/STATUS.md`)**
    *   *Evidence:* `STATUS.md` states Row 20 (CI unblock) is READY. `tick.log` shows the system launched `pri: 17` (`17-webjam-identity-line.md`). 
    *   *Why it fails:* Lexicographical/numerical sorting chooses `17` over `20`. The critical unblocker sits in the queue while feature work proceeds and fails against a dirty worktree.

### 4. Safety: Erosion of Hard Rules
**Can self-improvement erode the hard rules? YES.**
`worker.py` (Line 18) appends the hard rules to the LLM's prompt string. However, `PROMPT.md` gives the LLM root authorization to modify `bin/` and `services/` scripts. The LLM will eventually rewrite `worker.py` (to "optimize" it), accidentally stripping lines 18-22, freeing all sub-agents from your hard rules (spending limits, one-coder limits, no force-pushes). Furthermore, appending rules to the *end* of a prompt leaves you vulnerable to "ignore previous instructions" prompt-injection from external files.

**Proposed Guardrails:**
1.  **Immutable Rules File:** Move hard rules to `~/Documents/HARD_RULES.md`. Change its permissions (`chown root`, `chmod 444`). 
2.  **Read-Only Execution Core:** `chown root` and `chmod 555` on `worker.py`, `runtime.py`, and `jobs.py`. The LLM sandbox operates as your user and cannot modify them.
3.  **Strict Prepending:** In `worker.py`, *prepend* the rules: `prompt = HARD_RULES + "\n\n" + prompt`.

### 5. Ranked Top 10 Concrete Fixes
*(Ranked by High Impact vs Low Effort)*

1.  **Stop Self-Modification (System Survival)**
    *   *Change:* In `conductor/PROMPT.md`, delete Step 3 ("Self-improve: make ONE small, safe fix..."). Delete the entire `STANDING MANDATE` section. In `IMPROVE-ROUNDS.md`, change instruction to: "Assess only. Write findings to `improvements.md`. DO NOT MODIFY ANY SCRIPTS."
2.  **Fix Legacy Job Drop Bug (Data Loss)**
    *   *Change:* In `conductor/services/jobs.py` (Line 45), change `"BLOCKER.txt"` to `"ORPHAN_WARNING.txt"`. This prevents `closeout()` from accidentally reaping recovering jobs.
3.  **Prevent Orchestrator Hangs (SPOF)**
    *   *Change:* In `conductor/run-conductor.sh` (Lines 8-9), append `< /dev/null` to both CLI calls: `codex exec ... < /dev/null >> logs/conductor.log 2>&1 || claude ... < /dev/null >> logs/conductor.log 2>&1`.
4.  **Remove Hardcoded WebJam Path (Logic Block)**
    *   *Change:* In `conductor/services/worker.py` (Line 25), replace `cwd = Path.home() / "Documents/webjam-pr158-fold" if coding and "webjam" in job else folder` with `cwd = folder`. Jobs must operate in their own assigned directories.
5.  **Kill Dueling Orchestrators (Race Condition)**
    *   *Change:* `rm conductor/loop.sh`. In `/Users/jeffstory/Desktop/Bob-Takeover.command` (Line 9), delete the `elif ! screen -ls... loop.sh` fallback entirely. `start-all.sh` is sufficient.
6.  **Fix WebJam Git Sandbox Lockdown (Logic Block)**
    *   *Change:* In `worker.py` (Line 20), since Codex is sandboxed from git, force Claude for coding by changing: `engine = "claude" if coding else record.get("engine", "codex")`. 
7.  **Halt Token/Cost Runaway (Financial Limit)**
    *   *Change:* In `conductor/WEBJAM-UX-MAX.md` (Line 7), change `MANY passes... stop at about $48` to `EXACTLY 2 passes total. Do not loop.`.
8.  **Enforce Queue Priority (Logic Block)**
    *   *Change:* Rename the `next-prompts/INDEX.md` row for the CI fix from `20-webjam-ci-fix...` to `00-webjam-ci-fix...` so it sorts numerically first.
9.  **Protect Hard Rules from Prompt Injection (Safety)**
    *   *Change:* In `conductor/services/worker.py` (Lines 18-22), change `prompt += ("\nHard rules...` to `prompt = "HARD RULES: drafts only; never merge... \n\n" + prompt`.
10. **Fix STATUS.md File Contention (Race Condition)**
    *   *Change:* In `conductor/PROMPT.md` (Line 14), change `Overwrite conductor/STATUS.md` to `Append human decisions to conductor/JEFF-NEEDS.md`. Let `runtime.py` exclusively own the `STATUS.md` file.

### 6. Simplest Robust Target Design
You are over-complicating this with multi-agent councils and continuous system self-modification while unattended. Rip out the AI self-orchestration and rely strictly on deterministic Python.

```text
[ OS Cron / Launchd ] ---> [ watchdog.sh (Ensures Python Services Live) ]
                                  |
                                  v
[ Python: jobs.py ] <======> [ jobs.jsonl Queue ]
  (Picks next task)               |
        |                         v
        +-----[ screen -dmS worker ]---> (Claude/Codex CLI executes)
        |                                (Strict Timeout, CWD = Task Dir)
        v                                (Writes RESULT.txt or BLOCKER.txt)
[ Python: runtime.py ]
  (Compiles STATUS.md)
  (Pushes to Dashboard)
```
**Takeaway:** Stop trying to make the agents improve the orchestration while you are asleep. Lock down the Python scripts (chmod 444), feed the models a strict queue, and let them be dumb, reliable workers.
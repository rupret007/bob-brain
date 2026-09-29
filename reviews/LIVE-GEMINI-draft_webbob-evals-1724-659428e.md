A strict code review of branch `draft/webbob-evals-1724` at commit `659428e`.

The goal of this branch is to implement features to match or exceed the capabilities of a bot named "Bob the Bot," focusing on status reporting, job initiation, reply style, and other specific interactions. The branch introduces an evaluation framework to measure performance against these goals.

### Bugs and Security Issues (Ranked by Severity)

#### 1. CRITICAL BUG: Incomplete Evaluation Runner
*   **File**: `webchat/reply_builder.py`
*   **Line**: 141 (end of file)
*   **Issue**: The script `webchat/reply_builder.py`, which appears to be the engine for running the offline evaluations, is truncated. It defines helper classes (`ReplyOutcome`, `StubProviders`) and a utility function (`_seed_eval_root`) but is missing the core logic that would use these components to process a test case and generate a reply.
*   **Impact**: This makes the entire evaluation framework non-functional as-is. The primary deliverable of this branch—a way to evaluate replies—cannot be executed.
*   **Fix**: The complete implementation of `reply_builder.py` must be included in the branch. This would likely involve a main function or a primary entry point function that:
    1.  Loads the evaluation cases from `reply_eval_cases.json`.
    2.  For each case, sets up the application state and mocks (e.g., patching worker activity and LLM providers).
    3.  Invokes the chat logic (`app.Chat`).
    4.  Captures the generated reply and compares it against the defined rubrics.

#### 2. HIGH CONCERN: System Fails to Meet Core Goals
*   **File**: `reviews/WEBBOB-EVALS-0927.json`
*   **Line**: N/A (whole file)
*   **Issue**: The committed evaluation results show a pass rate of only **24/41 (58.5%)**. The failures directly contradict the stated goals of the project:
    *   **Goal: "plain-language job starts"**: Multiple `start` category tests (e.g., `start-01`, `start-08`, `start-13`) fail the `action_creates_jobs` rubric. The bot gives conversational replies without actually queueing any work.
    *   **Goal: "short answer-first replies"**: Numerous `status` and `llm` tests (e.g., `status-01`, `llm-03`) fail the `status_max_lines` rubric, indicating replies are too verbose.
    *   **Goal: "honest status naming"**: While the addition of the framework is a step towards this, the failures in job creation show a lack of "honest" action, which precedes status.
*   **Impact**: The evaluation framework, while a valuable addition, proves that the underlying system does not meet its primary objectives. Merging this branch would mean accepting a feature set that is demonstrably failing its own quality checks.
*   **Fix**: This is not a bug in the code added by this diff, but a failing grade for the system this diff evaluates. The underlying `app.py` dispatcher and state reporting logic must be fixed to pass these new, essential tests before the branch can be considered complete.

#### 3. MEDIUM BUG: Brittle Path Resolution
*   **File**: `webchat/mine_reply_eval_cases.py`
*   **Line**: 14-19
*   **Issue**: The `session_dir()` function uses a hardcoded, fragile method to locate the `sessions` directory by checking two fixed relative paths from the script's location (`CODE_ROOT / "..."` and `CODE_ROOT.parent.parent / "..."`). This can easily break if the project structure changes or the script is executed from an unexpected context.
*   **Fix**: Make the session directory path a required command-line argument using a standard library like `argparse`. This makes the script's dependency explicit and robust.
    ```python
    # Suggested change in mine_reply_eval_cases.py
    import argparse
    
    # ... remove session_dir() function ...
    
    def main() -> None:
        parser = argparse.ArgumentParser(description="Mine reply-quality eval cases from session logs.")
        parser.add_argument("session_dir", type=Path, help="Path to the conductor/webchat/sessions directory.")
        args = parser.parse_args()
    
        if not args.session_dir.is_dir():
            raise SystemExit(f"Error: Provided session directory does not exist: {args.session_dir}")
    
        # ...
        # Replace session_dir() call with args.session_dir
        for path in sorted(args.session_dir.glob("*.json")):
            # ...
    ```

### Security
No security vulnerabilities were identified in the code added by this diff. The scripts are developer tools that operate on local files and do not introduce new attack surfaces.

### Missing Tests
The purpose of this branch is to add a testing and evaluation framework. However, the scripts that constitute this framework (`mine_reply_eval_cases.py`, `reply_builder.py`) lack unit tests themselves. For developer tooling of this complexity, tests verifying the regex patterns and the reply builder's mocking logic would improve maintainability.

---
### VERDICT: FAIL

This branch is a commendable and necessary step towards creating a high-quality, regression-tested chatbot. The introduction of a structured evaluation framework with clear, goal-oriented rubrics is an excellent engineering practice.

However, the branch fails this review for two primary reasons:
1.  **It is incomplete.** The critical `reply_builder.py` script is non-functional as provided, which means the evaluation harness cannot be run.
2.  **It proves its own failure.** The included results demonstrate that the system fails to meet its core objectives more than 40% of the time. While adding failing tests is the first step to fixing bugs, this branch should remain a draft until it also includes the necessary fixes to achieve a much higher pass rate.
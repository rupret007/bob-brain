# GAPS progress — 1841 (draft/webbob-gaps-1725)

**When:** 2026-09-27 ~18:42 CDT  
**Base reviewed:** `3a7a571`  
**Branch:** `draft/webbob-gaps-1725` (draft only; no deploy/merge/undraft)

## Summary

Addressed LIVE-GEMINI and LIVE-MINIMAX **FAIL** findings: command-injection in screenshot AppleScript, platform/error-handling gaps, missing security and integration tests, and test-suite collisions with local web-search routing.

## Fixes

| Area | Change |
|------|--------|
| **CRITICAL — command injection** | `webchat/bob_gaps.py`: `_escape_applescript_string()`; `_macos_window_id()` escapes `\` and `"` before osascript interpolation. |
| **MEDIUM — macOS-only** | `capture_screenshot()` and `_macos_window_id()` raise `RuntimeError` when `sys.platform != "darwin"`. |
| **LOW — screencapture errors** | `capture_screenshot()` uses `capture_output=True` and surfaces stderr on non-zero exit. |
| **LOW — web search** | `web_search()` sends `User-Agent: WebBob/1.0 (bob-gaps web research)`. |
| **LOW — reply formatting** | `format_web_search_reply()` uses `.get()` for missing keys. |
| **Tests** | `webchat/test_bob_gaps.py`: injection escape, macOS gate, memory dismiss/stale/non-auto, search/screenshot failures, `/api/captures` HTTP, regex/parsers, ledger mismatch, User-Agent. |
| **Suite hygiene** | `test_failover.py` / `test_dispatch.py`: prompts no longer match `needs_web_search` so provider/failover paths are exercised. |

## Verification

```text
cd webchat && python3 -m unittest discover -p 'test_*.py' -q
# Ran 269 tests — OK
cd webchat && python3 -m unittest test_bob_gaps -v
# Ran 20 tests — OK
```

## Commit

Pushed on `draft/webbob-gaps-1725` after commit: *Harden bob_gaps screenshots and expand gap security tests.*

## Remaining risks / not done

- **File locking** on `append_profile_memory` (MINIMAX low): concurrent writers still possible; acceptable for single-user webchat per review.
- **Re-review:** Conductor LIVE-GEMINI / LIVE-MINIMAX should be re-run on the new HEAD to confirm PASS before gaps deploy.
- **Live DuckDuckGo** behavior not exercised in CI (mocked in unit/integration tests).

## Changed files (this pass)

- `webchat/bob_gaps.py`
- `webchat/test_bob_gaps.py`
- `webchat/test_failover.py`
- `webchat/test_dispatch.py`

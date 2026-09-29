# GAPS-FIXED-0004

**Branch:** draft/webbob-gaps-1725
**New tip SHA:** 953f440
**Prior tip SHA:** 70d59e3
**Verdict:** READY

## Gate finding

LIVE-MINIMAX-draft_webbob-gaps-1725-70d59e3.md FAILed the tip with 2 HIGH
issues in `webchat/bob_gaps.py` (Gemini's LIVE review of the same tip had
already passed the race/atomic fix from 70d59e3):

1. `_trim_profile_lines` (~line 67-73) recomputed `sum(len(entry) for entry
   in trimmed)` over the whole list on every `pop(0)`, making trims of a
   large profile file O(n²).
2. `append_profile_memory`'s `with (path.parent / "profile.lock").open("a")`
   (~line 96) had no graceful handling if the lock file couldn't be opened
   or locked — a `PermissionError`/`OSError` there would propagate with no
   context about which file/operation failed.

## Fix

- `_trim_profile_lines` now computes each line's byte length once, sums
  them into a running `total`, and advances a `start` cursor forward while
  subtracting from `total` — single pass, O(n) instead of O(n²). Matches
  the reviewer's suggested approach. Also switched from `len(entry)`
  (character count) to `len(entry.encode("utf-8"))` for a byte-accurate
  comparison against `PROFILE_MAX_BYTES`.
- `append_profile_memory` now opens the lock file and acquires `flock` in
  their own `try/except OSError` blocks, each re-raising with a message
  that names the lock path and the failing operation (open vs. acquire vs.
  write). The lock is unlocked and the file handle closed in `finally`
  blocks regardless of whether the body succeeds, so a lock/write failure
  no longer leaks an unreleased lock or a bare/unclear `OSError`. It still
  raises `OSError` (not a different exception type) so the existing
  call-site handling in `webchat/app.py` (`except OSError as exc:` around
  the "Could not save memory to profile" message) continues to catch it.

## Regression tests

Added to `webchat/test_bob_gaps.py`:

- `test_trim_profile_lines_keeps_newest_under_budget` — 5000 synthetic
  lines, asserts the trimmed result is exactly the newest slice under the
  byte budget.
- `test_trim_profile_lines_noop_when_under_budget` — confirms lines are
  left untouched when already under the limit.
- `test_append_profile_memory_lock_open_failure_raises_oserror` — makes
  `profile.lock` a directory (forcing `open("a")` to raise
  `IsADirectoryError`, an `OSError` subclass) and asserts
  `append_profile_memory` raises `OSError` with the lock path named in the
  message, instead of a bare/unclear traceback.

## Test run

`python3 -m unittest test_bob_gaps -v`: 27/27 OK (24 prior + 3 new).

`python3 -m unittest discover -s . -p "test_*.py" -v` (full webchat suite):
276/276 OK. (Some tests print `fatal: not a git repository` to stderr from
git calls inside the worktree — pre-existing noise unrelated to this
change; all tests still pass.)

## Files changed

- `webchat/bob_gaps.py` — `_trim_profile_lines` rewritten (O(n)),
  `append_profile_memory` lock handling hardened.
- `webchat/test_bob_gaps.py` — 3 new regression tests, added
  `_trim_profile_lines` to the import list.

## Push

Committed as `953f440` and pushed as a regular (non-force) push to
`brain/draft/webbob-gaps-1725` (`70d59e3..953f440`). No deploy, merge, or
undraft performed.

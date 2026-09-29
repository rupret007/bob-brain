# GAPS-FIXED-2143

**Branch:** draft/webbob-gaps-1725
**New tip SHA:** 70d59e3
**Prior tip SHA:** e62b6e3
**Verdict:** READY

## Gate finding

LIVE-GEMINI-draft_webbob-gaps-1725-e62b6e3.md flagged a race in
`append_profile_memory` (webchat/bob_gaps.py): the append (open+write) and
the trim (`_trim_profile_file`, a separate read_text/write_text pair) were
two unlocked, non-atomic file operations. Concurrent "remember that"
confirmations could interleave and lose a memory line.

## Fix

- Merged the append and trim into a single critical section guarded by
  `fcntl.flock(LOCK_EX)` on a sibling `profile.lock` file, matching the
  existing lock pattern used elsewhere in webchat (e.g. `actions.py`'s
  `queue_once`).
- Replaced the trailing `path.write_text(...)` with `failover.atomic_text`
  (write to a temp file in the same directory, fsync, `os.replace`, fsync
  parent dir) so the on-disk file is never observed half-written.
- `_trim_profile_file` (path-based, did its own I/O) was replaced with
  `_trim_profile_lines` (pure, operates on an in-memory list) so trimming
  happens inside the same lock/read/write instead of as a second unlocked
  pass.

## Regression test

Added `test_append_profile_memory_concurrent_appends_not_lost` to
`webchat/test_bob_gaps.py`: spins up 12 threads behind a `threading.Barrier`
so they all call `append_profile_memory` at once, then asserts all 12
distinct lines are present in the final profile file with no exceptions
raised. This reproduces the lost-write window against the old
read-then-write-without-lock code (verified failing before the fix, passing
after).

## Test run

Ran the full webchat unit test suite (unittest, not pytest — pytest isn't
installed in this environment):

```
test_api_call        1 test    OK
test_bob_gaps        24 tests  OK  (incl. new concurrency regression test)
test_build_info      4 tests   OK
test_chat_intent     27 tests  OK
test_dispatch        37 tests  OK
test_failover        25 tests  OK
test_jobs_view       16 tests  OK
test_reply_authority 13 tests  OK
test_tab_status      8 tests   OK
test_webchat         94 tests  OK
test_worker_activity 9 tests   OK
```

(`test_live_*` suites were not run — they exercise live/deployed
integration paths outside this fix's scope.)

## Push

Committed and pushed as a regular (non-force) push to
`brain/draft/webbob-gaps-1725`. No deploy, merge, or undraft performed.

You are Claude on Jeff's Mac Mini. Work ONLY in:
  ~/Documents/bob-overnight-inject/workspaces/webbob-gaps-1725
Branch: draft/webbob-gaps-1725 @ e62b6e3. Drafts only. No deploy/merge/undraft/force-push. No secrets. Never use Grok.

GATE: LIVE-GEMINI-draft_webbob-gaps-1725-e62b6e3.md VERDICT FAIL — race in append_profile_memory (non-atomic read-modify-write + separate _trim_profile_file). Concurrent "remember that" confirmations can lose a memory.

Fix: make append_profile_memory + trim atomic under the provided lock (single critical section; hold lock across read/append/trim/write). Add a regression test that simulates concurrent appends (or lock-contended sequential equivalent proving no lost lines). Run webchat unit tests (esp. test_bob_gaps). Commit + regular-push draft/webbob-gaps-1725. Write ~/Documents/bob-overnight-inject/conductor/reviews/GAPS-FIXED-2143.md with new tip SHA and READY/STILL-FAIL. No Jeff notify.

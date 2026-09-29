You are Claude on Jeff's Mac Mini. Work ONLY in:
  ~/Documents/bob-overnight-inject/workspaces/webbob-gaps-1725
Branch: draft/webbob-gaps-1725 @ current tip (was 70d59e3). Drafts only. No deploy/merge/undraft/force-push. No secrets. Never use Grok/xAI.

GATE: LIVE MiniMax FAIL on tip 70d59e3 with 2 HIGH issues still open:
1. O(n^2) trim logic in webchat/bob_gaps.py (~67-73)
2. No graceful handling of lock file write failures (~line 96)
Gemini LIVE already PASS on the race/atomic fix.

Fix both HIGH issues on the same branch, push a new tip (regular push only), run webchat tests focused on bob_gaps, write ~/Documents/bob-overnight-inject/conductor/reviews/GAPS-FIXED-0004.md with READY or FAIL, new SHA, test counts, files changed. Do not deploy. Do not notify Jeff.

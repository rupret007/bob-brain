# Self-improvement round 3 (Cursor lane, then Gemini+MiniMax critique; no Grok, Claude short only)
Read reviews/SELF-IMPROVE-R2-RESULT.md (holes 4-5 left open) and current logs/STATUS.
1. Fix hole 4: lanes idle while backlog READY. Make the scheduler actually launch queued non-WebJam work (StoryBoard, AdoptIQ #26 rebase) when Codex/Cursor free; keep one WebJam coder max.
2. Fix hole 5: watchdog PermissionError on /tmp lock probe; handle gracefully.
3. Fix the council Codex synthesize BlockingIOError (council/pr161 log).
4. Webchat reply showed "queued" with no provider for a while; if svc-webchat-failover is still running do NOT touch conductor/webchat, just note it.
Private worktree, draft branch off draft/self-improve-r2, regression test each, all tests pass. Then run council.py critique of your diff (Gemini+MiniMax, Claude short) and apply valid points.
Never merge/undraft/force-push; no texts/emails; caps respected.
Write conductor/reviews/SELF-IMPROVE-R3-RESULT.md: fixes, PASS/FAIL, SHA, anything Jeff must do.

You are Cursor Agent on Jeff's Mac Mini. Work ONLY in:
  ~/Documents/bob-overnight-inject/workspaces/wt-webbob-media-0927
Branch: draft/webbob-media-0927 @ 829d45c. Drafts only. No deploy/merge/undraft/force-push. No secrets. Never use Grok/xAI.

Read:
  ~/Documents/bob-overnight-inject/conductor/reviews/LIVE-MINIMAX-draft_webbob-media-0927-829d45c.md
  (VERDICT FAIL — critical blockers listed at end)

SCOPE — fix ONLY these real CRITICAL/HIGH from that MiniMax review (triage against REAL code first; skip false positives):
1. app.py upload: Content-Length vs rfile.read race / unbounded hang — cap read at declared limit; reject incomplete/mismatched size safely.
2. chat_media.py secret scan bypass for binary files — scan raw bytes / filename robustly so embedded secrets in binary cannot slip past redact; do NOT invent OCR dependency if not already in tree; prefer scanning raw bytes + filename with existing redact helpers.
3. chat_media.py enrich_for_model PROCESS_SLOTS semaphore leak — only release a slot you acquired; on acquire timeout/failure do NOT release; ensure try/finally only wraps successful acquire.
4. chat_media.py store_media orphan blob if metadata write fails — cleanup blob on metadata failure.

Ignore out-of-lane voice barge-in, XSS/markdown, draft-yes-send (other branches), iPhone UI gaps unless they are the four criticals above.
Add focused regression tests for the real fixes.
Run webchat (+ services if touched) pytest. Commit + regular-push (never force-push) if changes.
Write ~/Documents/bob-overnight-inject/conductor/reviews/MEDIA-FIXED-2205.md with tip SHA, test counts, READY or STILL-FAIL, and which criticals fixed. No Jeff notify.

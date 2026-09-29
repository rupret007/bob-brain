You are Codex on Jeff's Mac Mini. Work ONLY in:
  ~/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420
Branch: draft/webbob-texting-onto-a777736 (starts at live integrate tip a777736).
Drafts only. No deploy. No merge into draft/webbob-clean-0927. No undraft. No force-push. No secrets. No STOP-WEBBOB. Do not notify Jeff. Do not text anyone. Do not touch live conductor pins or production.

GOAL: Produce a combined tip that is live integrate a777736 PLUS texting tip 9751346, so Web Bob can ship texting without regressing integrate.

CONTEXT:
- Live prod SHA is a777736 (integrate BOTH_PASS, deployed).
- Isolated texting tip 97513468016488ebe42ca1919e507db99fc0a15f on draft/webbob-texting-0927 has BOTH_PASS (Gemini+MiniMax TEXTING-REREVIEW-2143) and offline READY (295 webchat / 121 services) — but merge into clean conflicts.
- Known conflicts: webchat/app.py (must KEEP integrate worker_assignment / status_reply / reply_authority / status_observation AND ADD texting.handle / Texting() / public filtering / actor on submit) and reviews/WEBBOB-EVALS-0927.md (union both sides honestly).
- Source texting worktree (read-only reference): ~/Documents/bob-overnight-inject/workspaces/wt-webbob-texting-0927 @ 9751346
- HOLD marker: ~/Documents/bob-overnight-inject/conductor/reviews/TEXTING-MERGE-HOLD-0420.md

STEPS:
1. Fetch brain/draft/webbob-texting-0927. Merge 9751346 into this worktree (or equivalently merge that tip). Resolve conflicts carefully:
   - In app.py: preserve integrate's status_reply, worker_assignment requested_workers / issue_followup, and related imports. Wire texting as on the texting tip: import Texting, self.texting, texting.public in public(), texting.handle early in submit with persist_texting clearing pending_job keys, actor param on submit. Do NOT drop integrate job routing.
   - In WEBBOB-EVALS-0927.md: keep both feature notes without claiming false scores.
   - Bring over all texting source/tests/static assets from 9751346 (texting.py, test_texting*.py, texting_fixture.py, texting_proof.py, browser_texting.cjs, static card bits, reviews screenshots/evidence as already in tip).
2. Run: python3 -m unittest discover -s webchat -p 'test_*.py'; python3 -m unittest discover -s services -p 'test_*.py'; node --check webchat/static/app.js; git diff --check. Fix any real breakages from the merge.
3. Commit on draft/webbob-texting-onto-a777736 with a clear message. Regular-push to brain (no force). Record full SHA.
4. Write markers into BOTH this worktree's conductor/reviews/ (if present) AND ~/Documents/bob-overnight-inject/conductor/reviews/:
   - TEXTING-FIXED-0420.md (conflict dispositions, what was kept from each side, test counts, tip SHA)
   - TEXTING-READY-0420.md if suites green (READY for fresh LIVE Gemini+MiniMax on the NEW combined SHA; does NOT authorize deploy)
   - or TEXTING-STILL-FAIL-0420.md if blocked
5. Do not open/merge/undraft PRs unless needed for a regular push of this draft branch only. Prefer leaving draft/webbob-texting-0927 and draft/webbob-clean-0927 untouched.
6. Stop when READY or STILL-FAIL markers are written. No deploy.

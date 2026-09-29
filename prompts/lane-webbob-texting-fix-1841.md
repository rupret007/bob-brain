You are Codex on Jeff's Mac Mini. Work ONLY in:
  ~/Documents/bob-overnight-inject/workspaces/wt-webbob-texting-0927
Branch: draft/webbob-texting-0927 (currently 8f82fc0). Drafts only — never merge/undraft/force-push. Never print webchat/.password. Do not create ~/STOP-WEBBOB. Do not deploy or restart services.

GOAL: Make texting deploy-ready for the next conductor loop.

Read first:
- ../../conductor/reviews/TEXTING-GATE-FAIL-0927.md
- ../../conductor/reviews/LIVE-GEMINI-draft_webbob-texting-0927-8f82fc0.md
- ../../conductor/reviews/LIVE-MINIMAX-brain_draft_webbob-texting-0927-8f82fc0.md
- reviews/TEXTING-READY-0927.md and reviews/TEXTING-FIXED-0927.md (prior work)

Required fixes:
1. Harmonize E2E proof: browser_texting.cjs vs committed evidence/screenshots. Either regenerate mock-send evidence ("Sent via Andrea") to match the script, OR update script+docs so blocked "Not sent" path is the honest proof. No contradictory artifacts.
2. app.py public(): apply core exclusions (codex_thread_id, retry_prompt, pending_job, pending_job_id, held_job) BEFORE or independently of texting.public(); ensure deep copy; no sensitive leak.
3. Confirm hmac.compare_digest for yes-token compare (already present — keep/strengthen); add test_separate_yes_success_message_content for mock Andrea success path; add error-scrubbing test if missing.
4. Remove duplicate self.save after texting.handle if persist_texting already saves.
5. Rebase or merge onto live tip dff84e3 (brain/draft/webbob-replies-1720 or whatever tracks live) carefully; resolve conflicts; stay on draft/webbob-texting-0927.
6. Run full tests from worktree root:
     python3 -m unittest discover -s webchat -p 'test_*.py'
     python3 -m unittest discover -s services -p 'test_*.py'
     node --check webchat/static/app.js
   Fix failures.
7. Commit (draft branch) and push to brain remote draft/webbob-texting-0927 (regular push OK, no force).
8. Write markers:
     reviews/TEXTING-FIXED-1841.md  (what changed)
     ../../conductor/reviews/TEXTING-FIXED-1841.md (copy)
   If you believe deploy-ready: also reviews/TEXTING-READY-1841.md with tip SHA + test counts. Else reviews/TEXTING-STILL-FAIL-1841.md with remaining blockers.

Do NOT notify Jeff. Stay in this worktree.

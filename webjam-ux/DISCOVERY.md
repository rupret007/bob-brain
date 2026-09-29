# Read-only discovery and preservation receipt

Repository: https://github.com/rupret007/webjam
Original worktree: /Users/jeffstory/Documents/webjam-pr158-fold
Original branch: codex/rehearsal-recap-card
Original HEAD: 6b8d069a5f4e5999c98e23aaffca2f64c11f5c46
Tracked dirty file: tests/test_art_host_platforms.py (one line).
Untracked ci-fix-choice-helper-closeout/ was not copied or committed.

The original worktree and its Git metadata are outside the session writable roots.
An independent clone in conductor/webjam-ux/repo copied the exact tracked fix.
33 platform tests passed with QT_QPA_PLATFORM=offscreen and the existing Python environment.
Normal fast-forward push to codex/rehearsal-recap-card succeeded at 5bddcd2.
The original worktree still has its local dirty edit; it has not been reset or cleaned.
The remote now preserves that edit. Jeff can later fast-forward/reconcile the original checkout.

Competing identity job: webjam-identity-line-2238/cursor.log shows authentication
required; run.sh uses set -euo pipefail and stopped before editing. Its stale
screen is not an active coder. UX code is authored only by this Codex session.

#159 correction: branch selection failed during preservation, and a push briefly
advanced #159 to #160's 5bddcd2. Corrected without any force push: 86c9a30 restores
#159 to exactly original 885a324's tree plus the intended one-line test fix.
Both #159 and #160 preservation tests passed (33 each). The correction remains
visible in #159 history; neither draft was merged or undrafted.
UX branch codex/ux-max-pass starts from #160's preserved 5bddcd2, so it retains
both host checklist and rehearsal recap. It will be a draft stacked on #160.

To preserve future draft ancestry, #160 then received a normal forward commit 48007f88ca0f524531b0c2f672286d7fcc78f938 restoring the recap atop #159 correction. Its tree is byte-for-byte identical to tested 5bddcd2. UX branch was advanced before any UI edits. No merge command or force push was used.

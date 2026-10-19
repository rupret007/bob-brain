#!/bin/zsh
# Safe disk cleanup. NEVER delete Playwright browser builds a repo's pinned version needs
# (Web Bob gate: chromium-1148, webkit-2104 under ~/bob-scratch/pw-browsers and any
# ~/Library/Caches/ms-playwright/{chromium,webkit,ffmpeg,chromium_headless_shell}-*).
b=$(df -k / | awk 'NR==2{print $4}')
/opt/homebrew/bin/brew cleanup -s --prune=7 >/dev/null 2>&1
npm cache clean --force >/dev/null 2>&1; pip3 cache purge >/dev/null 2>&1
# Caches only — never ms-playwright or bob-scratch/pw-browsers
rm -rf ~/Library/Caches/pip ~/Library/Caches/node-gyp ~/.cache/pip 2>/dev/null
# Explicit keep list (do not rm these paths even in future ad-hoc cleanups):
#   ~/bob-scratch/pw-browsers/chromium-1148
#   ~/bob-scratch/pw-browsers/webkit-2104
#   ~/Library/Caches/ms-playwright
find ~/Library/Developer/Xcode/DerivedData -mindepth 1 -maxdepth 1 -mtime +3 -exec rm -rf {} + 2>/dev/null
for g in ~/Documents/*/.git(N/); do git -C ${g:h} worktree prune 2>/dev/null; done
# merged proj-max worktrees whose branch is merged into origin/main
for wt in ~/Documents/proj-max/wt/*(N/); do br=$(git -C $wt branch --show-current 2>/dev/null); [ -n "$br" ] || continue; [ -z "$(git -C $wt status --porcelain 2>/dev/null)" ] || continue; git -C $wt fetch -q origin main 2>/dev/null; git -C $wt merge-base --is-ancestor HEAD origin/main 2>/dev/null && { src=$(git -C $wt rev-parse --git-common-dir); git -C $wt worktree remove "$wt" && echo "removed merged $wt"; }; done
find ~/lane-wt/q-* ~/lane-wt/c-* -maxdepth 3 -name node_modules -prune -mtime +1 2>/dev/null | head -0
a=$(df -k / | awk 'NR==2{print $4}'); echo "$(date) cleanup freed_MB=$(( (a-b)/1024 )) free=$(df -h / | awk 'NR==2{print $4}')"

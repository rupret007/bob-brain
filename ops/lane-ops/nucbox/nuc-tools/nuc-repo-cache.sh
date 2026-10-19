#!/bin/bash
# nuc-repo-cache.sh OWNER/REPO DEST [PR]   (lane-ops v3, arch-review-2 capacity item 7)
# Gives a job a fresh git worktree at DEST from ONE cached bare clone per repo (~/work/.mirrors/OWNER__REPO.git),
# instead of `rm -rf; gh repo clone --depth 80` for every job. The cache is fetched (under a per-repo flock) on each
# call, DEST is a detached worktree at the PR head (PR given) or the default branch. Pushes from DEST must name the
# branch: `git push origin HEAD:refs/heads/<branch>` (no mirror refspec, so a bare `git push` pushes nothing extra).
# Exit 0 ok, 4 clone/fetch failure, 5 PR head fetch failure, 2 usage. Prints the checked-out SHA on stdout.
R=$1; DEST=$2; PR=${3:-}
[ -n "$R" ] && [ -n "$DEST" ] || { echo "usage: nuc-repo-cache.sh OWNER/REPO DEST [PR]" >&2; exit 2; }
case $R in */*) ;; *) echo "repo must be OWNER/REPO" >&2; exit 2;; esac
case $R$PR in *[!A-Za-z0-9._/-]*) echo "bad repo/pr" >&2; exit 2;; esac
C=${NUC_REPO_CACHE:-$HOME/work/.mirrors}; mkdir -p "$C"
URL=${NUC_REPO_URL_BASE:-https://github.com}/$R.git
M=$C/${R//\//__}.git
exec 8>"$M.lock"; flock -w "${NUC_REPO_CACHE_LOCK_WAIT:-600}" 8 || { echo "CACHE lock timeout $M" >&2; exit 4; }
if [ ! -d "$M/objects" ]; then
  rm -rf "$M"
  git clone -q --bare "$URL" "$M" >&2 || { echo "CACHE clone failed $R" >&2; rm -rf "$M"; exit 4; }
  git -C "$M" config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
  git -C "$M" config gc.auto 0   # gc by hand only; never repack under a running worktree
fi
git -C "$M" fetch -q --prune origin >&2 || { echo "CACHE fetch failed $R" >&2; exit 4; }
def=$(git -C "$M" symbolic-ref --short HEAD 2>/dev/null); def=${def#refs/heads/}; def=${def:-main}
git -C "$M" rev-parse -q --verify "refs/remotes/origin/$def" >/dev/null && git -C "$M" symbolic-ref refs/remotes/origin/HEAD "refs/remotes/origin/$def"
ref=refs/remotes/origin/$def
if [ -n "$PR" ]; then
  git -C "$M" fetch -q origin "+refs/pull/$PR/head:refs/remotes/origin/pr/$PR" >&2 || { echo "CACHE PR #$PR fetch failed" >&2; exit 5; }
  ref=refs/remotes/origin/pr/$PR
fi
if [ -e "$DEST" ]; then git -C "$M" worktree remove --force "$DEST" >/dev/null 2>&1 || rm -rf "$DEST"; fi
git -C "$M" worktree prune
git -C "$M" worktree add -q --detach "$DEST" "$ref" >&2 || { echo "CACHE worktree add failed $DEST" >&2; exit 4; }
git -C "$DEST" rev-parse HEAD

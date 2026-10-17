#!/bin/bash
# gemini-ctx.sh JOB REPO PR  (22:10 CT 10/16) — NucBox side of Gemini lanes: clone+checkout, print a context bundle on stdout.
# Extra paths (one per line) on stdin. Exit 4 clone fail, 5 checkout fail (bundle still printed for reviews).
J=$1; R=$2; PR=$3; W=~/work/gem-ctx-$J; rc=0
. ~/.nvm/nvm.sh >/dev/null 2>&1
extra=$(cat)
# lane-ops v3 (capacity): worktree from the cached bare clone (nuc-repo-cache.sh) instead of a fresh clone per job
if [ -n "$PR" ]; then
  bash ~/nuc-tools/nuc-repo-cache.sh $R $W $PR >/dev/null 2>&1; c=$?
  if [ $c = 5 ]; then bash ~/nuc-tools/nuc-repo-cache.sh $R $W >/dev/null 2>&1 || exit 4; rc=5; elif [ $c != 0 ]; then exit 4; fi
else
  bash ~/nuc-tools/nuc-repo-cache.sh $R $W >/dev/null 2>&1 || exit 4
fi
cd $W
emit(){ [ -f "$1" ] || return; echo "--- FILE $1 ---"; head -c 200000 "$1"; echo; }
if [ -n "$PR" ]; then
  echo "--- FILE PR-$PR.diff ---"; gh pr diff $PR -R $R 2>/dev/null | head -c 80000; echo
  gh pr diff $PR -R $R --name-only 2>/dev/null | head -25 | while read f; do emit "$f"; done
fi
emit README.md
printf '%s\n' "$extra" | sort -u | while read f; do [ -n "$f" ] && emit "$f"; done
git ls-files | grep -E '(test|spec)' | head -6 | while read f; do emit "$f"; done
exit $rc

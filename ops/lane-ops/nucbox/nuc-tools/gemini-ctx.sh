#!/bin/bash
# gemini-ctx.sh JOB REPO PR  (22:10 CT 10/16) — NucBox side of Gemini lanes: clone+checkout, print a context bundle on stdout.
# Extra paths (one per line) on stdin. Exit 4 clone fail, 5 checkout fail (bundle still printed for reviews).
J=$1; R=$2; PR=$3; W=~/work/gem-ctx-$J; rc=0
. ~/.nvm/nvm.sh >/dev/null 2>&1
extra=$(cat)
rm -rf $W; gh repo clone $R $W -- --depth 60 --no-single-branch -q >/dev/null 2>&1 || exit 4
cd $W
emit(){ [ -f "$1" ] || return; echo "--- FILE $1 ---"; head -c 60000 "$1"; echo; }
if [ -n "$PR" ]; then
  gh pr checkout $PR >/dev/null 2>&1 || { git fetch -q --depth 60 origin pull/$PR/head:gem-pr-$PR && git checkout -q gem-pr-$PR; } || rc=5
  echo "--- FILE PR-$PR.diff ---"; gh pr diff $PR 2>/dev/null | head -c 80000; echo
  gh pr diff $PR --name-only 2>/dev/null | head -25 | while read f; do emit "$f"; done
fi
emit README.md
printf '%s\n' "$extra" | sort -u | while read f; do [ -n "$f" ] && emit "$f"; done
git ls-files | grep -E '(test|spec)' | head -6 | while read f; do emit "$f"; done
exit $rc

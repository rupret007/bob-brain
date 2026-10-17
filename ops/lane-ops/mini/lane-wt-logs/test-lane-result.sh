#!/bin/zsh
# tests for lane-result.sh (v6.4)
T=$(mktemp -d); export LANE_LOG_DIR=$T; R=~/lane-wt/logs/lane-result.sh; fail=0
ck(){ grep -q "$2" $T/$1.log && echo "ok $1" || { echo "FAIL $1"; fail=1; }; }
printf 'gemini-lane x mode=review\n1. finding a.py:3\nASSESS_BLOCKED\nEXIT 0\n' > $T/a.log; $R $T/a.log a; ck a 'RESULT gemini-review (recovered) verdict=ASSESS_BLOCKED'
printf 'gemini-lane x\nEXIT 0\n' > $T/b.log; printf 'review\nASSESS_OK\n' > $T/q-b.gemini.md; $R $T/b.log b; ck b 'verdict=ASSESS_OK'
printf 'RESULT gemini-review rc=0\nEXIT 0\n' > $T/c.log; $R $T/c.log c; [[ $(grep -c '^RESULT' $T/c.log) == 1 ]] && echo "ok c" || { echo FAIL c; fail=1; }
printf 'gemini-lane: fallback to cursor-agent\nEXIT 0\n' > $T/d.log; $R $T/d.log d; ck d 'RESULT cursor-fallback exit=0'
printf 'gemini-lane x\nEXIT 1\n' > $T/e.log; $R $T/e.log e; ck e '^BLOCKER no RESULT line'
printf 'BLOCKER gemini paused\n' > $T/f.log; $R $T/f.log f; [[ $(wc -l < $T/f.log) -eq 1 ]] && echo "ok f" || { echo FAIL f; fail=1; }
rm -rf $T; exit $fail

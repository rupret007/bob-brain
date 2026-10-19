#!/bin/zsh
# tests for lane-result.sh (v6.4; lane-ops v3 B4: fallback exit 0 and empty pr= are BLOCKERs, exit code follows outcome)
T=$(mktemp -d); export LANE_LOG_DIR=$T; R=${LANE_RESULT_SH:-${0:A:h}/lane-result.sh}; fail=0
ck(){ grep -q "$2" $T/$1.log && echo "ok $1" || { echo "FAIL $1"; fail=1; }; }
rc(){ [[ $2 == $3 ]] && echo "ok $1 rc" || { echo "FAIL $1 rc=$2 want $3"; fail=1; }; }
printf 'gemini-lane x mode=review\n1. finding a.py:3\nASSESS_BLOCKED\nEXIT 0\n' > $T/a.log; $R $T/a.log a; rc a $? 0; ck a 'RESULT gemini-review (recovered) verdict=ASSESS_BLOCKED'
printf 'gemini-lane x\nEXIT 0\n' > $T/b.log; printf 'review\nASSESS_OK\n' > $T/q-b.gemini.md; $R $T/b.log b; rc b $? 0; ck b 'verdict=ASSESS_OK'
printf 'RESULT gemini-review rc=0\nEXIT 0\n' > $T/c.log; $R $T/c.log c; rc c $? 0; [[ $(grep -c '^RESULT' $T/c.log) == 1 ]] && echo "ok c" || { echo FAIL c; fail=1; }
printf 'gemini-lane: fallback to cursor-agent\nEXIT 0\n' > $T/d.log; $R $T/d.log d; rc d $? 1; ck d '^BLOCKER unverified cursor-fallback exit=0'
grep -q '^RESULT' $T/d.log && { echo "FAIL d: fallback must not count as RESULT"; fail=1; } || echo "ok d no RESULT"
printf 'gemini-lane x\nEXIT 1\n' > $T/e.log; $R $T/e.log e; rc e $? 1; ck e '^BLOCKER no RESULT line'
printf 'BLOCKER gemini paused\n' > $T/f.log; $R $T/f.log f; rc f $? 1; [[ $(wc -l < $T/f.log) -eq 1 ]] && echo "ok f" || { echo FAIL f; fail=1; }
printf 'RESULT pr= head=abc Fri\n' > $T/g.log; $R $T/g.log g; rc g $? 1; ck g '^BLOCKER RESULT has no PR'
printf 'RESULT pr=https://github.com/o/r/pull/7 head=abc\n' > $T/h.log; $R $T/h.log h; rc h $? 0; [[ $(wc -l < $T/h.log) -eq 1 ]] && echo "ok h" || { echo FAIL h; fail=1; }
printf 'RESULT branch=b pr=\n' > $T/i.log; $R $T/i.log i; rc i $? 1
rm -rf $T; exit $fail

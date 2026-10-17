#!/bin/zsh
# lane-result.sh LOG JOB  (v6.4 22:12 CT 10/16) — called at lane exit. If no RESULT/BLOCKER line, recover one:
#  Gemini review whose output has ASSESS_OK/ASSESS_BLOCKED (log or q-JOB.gemini.md) -> RESULT gemini-review (recovered)
#  cursor fallback that exited 0 -> RESULT cursor-fallback exit=0 (needs check)   ; else BLOCKER no RESULT line
LOG=$1; J=$2; D=${LANE_LOG_DIR:-$HOME/lane-wt/logs}
grep -qE '^(RESULT|BLOCKER)' $LOG 2>/dev/null && exit 0
md=$D/q-$J.gemini.md
if grep -qE 'ASSESS_(OK|BLOCKED)' $LOG 2>/dev/null || { [[ -s $md ]] && grep -qE 'ASSESS_(OK|BLOCKED)' $md; }; then
  v=$(cat $LOG $md 2>/dev/null | grep -oE 'ASSESS_(OK|BLOCKED)' | tail -1)
  echo "RESULT gemini-review (recovered) verdict=$v out=$md" >> $LOG; exit 0; fi
if grep -q 'fallback to cursor-agent' $LOG && grep -qE '^EXIT 0$' $LOG; then
  echo "RESULT cursor-fallback exit=0 (no structured RESULT; check branch/PR before trusting)" >> $LOG; exit 0; fi
echo 'BLOCKER no RESULT line' >> $LOG

#!/bin/zsh
# lane-result.sh LOG JOB  (v6.4 22:12 CT 10/16) — called at lane exit. If no RESULT/BLOCKER line, recover one:
#  Gemini review whose output has ASSESS_OK/ASSESS_BLOCKED (log or q-JOB.gemini.md) -> RESULT gemini-review (recovered)
#  anything else -> BLOCKER
# lane-ops v3 (arch-review-2 B4): success counts must mean something.
#  * A cursor fallback that merely exited 0 is no longer a RESULT: it is logged as
#    "BLOCKER unverified cursor-fallback exit=0 ..." (it used to print RESULT and inflate success counts).
#  * A RESULT whose pr= is empty (pushed, but no PR was created) gets a BLOCKER line appended.
#  * Exit status: 0 when the log ends with a usable RESULT, 1 when the outcome is a BLOCKER, so the screen's exit
#    code (and lane-lease.sh's release status DONE/FAILED) follows the real outcome.
LOG=$1; J=$2; D=${LANE_LOG_DIR:-$HOME/lane-wt/logs}
ok_result(){ grep -E '^RESULT' $LOG 2>/dev/null | tail -1 | grep -vqE '(^|[[:space:]])pr=([[:space:]]|$)'; }
if grep -qE '^RESULT' $LOG 2>/dev/null; then
  ok_result && exit 0
  echo 'BLOCKER RESULT has no PR (pr= empty): pushed but no PR, or the PR step failed' >> $LOG; exit 1
fi
grep -qE '^BLOCKER' $LOG 2>/dev/null && exit 1
md=$D/q-$J.gemini.md
if grep -qE 'ASSESS_(OK|BLOCKED)' $LOG 2>/dev/null || { [[ -s $md ]] && grep -qE 'ASSESS_(OK|BLOCKED)' $md; }; then
  v=$(cat $LOG $md 2>/dev/null | grep -oE 'ASSESS_(OK|BLOCKED)' | tail -1)
  echo "RESULT gemini-review (recovered) verdict=$v out=$md" >> $LOG; exit 0; fi
if grep -q 'fallback to cursor-agent' $LOG && grep -qE '^EXIT 0$' $LOG; then
  echo "BLOCKER unverified cursor-fallback exit=0 (no structured RESULT; check branch/PR by hand)" >> $LOG; exit 1; fi
echo 'BLOCKER no RESULT line' >> $LOG
exit 1

#!/bin/bash
# usage: nuc-lane.sh NAME REPO BRANCH BASE WORKID [WAIT_SCREEN] ; prompt at ~/lane-wt/logs/NAME.prompt
# v6.5: LANE_PROVIDER=cursor|codex (default cursor). Codex uses Windows CLI on NucBox (gpt-6-astra). LANE_TIER=cheap|high; LANE_MODEL for cursor (composer-2.5). LANE_EFFORT for codex (high|xhigh|medium).
# lane-ops v3 (arch-review-2):
#  * B2/B3: the lane body runs under lane-lease.sh (renew failure stops the lane; every exit releases the claim) and
#    the NucBox side runs under lane-supervise.sh (stopped on release, self-stops when heartbeats stop). Before
#    `gh pr create` the claim is checked (fence), so a lane that lost its lease can't open a PR.
#  * B4: no PR = no success. If the branch was pushed but pre-pr refused or `gh pr create` failed, the lane logs
#    BLOCKER and releases FAILED (it used to log `RESULT pr=` with an empty PR and release DONE).
#  * B8: a BLOCKED claim (rc 3) is retried 3 times with short backoff (~1.5 min total), not 6 x 300 s inside a
#    counted screen slot.
#  * item 10: no Mini fallback. If the NucBox is unreachable the lane is HELD and releases its claim.
D=${LANE_LOG_DIR:-$HOME/lane-wt/logs}; G=${CLAIM_GATE:-$HOME/Documents/bob-overnight-inject/bin/claim-gate.py}
OWNER=${NUC_LANE_OWNER:-grok-exec-games-1616}
SSH=${NUC_SSH:-"ssh -o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=30 -i $HOME/.ssh/nuc_ed25519 -p 2222 rupret@nuc-wsl"}
GH=${GH:-gh}
if [ "${1:-}" = "--inner" ]; then
  shift; N=$1 R=$2 B=$3 BASE=$4 W=$5; L=$D/$N.log
  LG=${LANE_GUARD:-$HOME/bin/lane-guard.sh}; [ -f "$LG" ] && . "$LG"
  PROV=${LANE_PROVIDER:-cursor}; M=$NL_MODEL; EFF=$NL_EFF; TIER=${LANE_TIER:-cheap}
  if ! $SSH true </dev/null 2>/dev/null; then
    echo "HOLD nucbox unreachable; no Mini fallback (arch-review-2 item 10) $(date)" >>$L
    echo "BLOCKER nucbox unreachable (held, not run on the Mini)" >>$L; exit 1
  fi
  echo "HOST nucbox provider=$PROV $(date)" >>$L
  $SSH "mkdir -p ~/work/results ~/work/$N && cat > ~/work/results/$N.prompt" < $D/$N.prompt
  LS=${LANE_LEASE_S:-900}
  if [ "$PROV" = codex ]; then
    $SSH "bash -l ~/nuc-tools/lane-supervise.sh run $N $LS -- bash -l ~/nuc-tools/lane-run-codex.sh $N $EFF" </dev/null >>$L 2>&1; xrc=$?
  else
    $SSH "bash -l ~/nuc-tools/lane-supervise.sh run $N $LS -- bash -l ~/nuc-tools/lane-run.sh $N $R $B $BASE $M" </dev/null >>$L 2>&1; xrc=$?
  fi
  [ "$xrc" = 143 ] && { echo "BLOCKER remote lane stopped (lease lost or released) $(date)" >>$L; exit 1; }
  type gh_throttle >/dev/null 2>&1 && gh_throttle >>$L 2>&1
  HEAD=$(git ls-remote https://github.com/rupret007/$R.git refs/heads/$B 2>/dev/null | cut -f1)
  [ -z "$HEAD" ] && { echo "BLOCKER no branch pushed ($B)" >>$L; exit 1; }
  PR=$($GH pr list -R rupret007/$R --head $B --state open --json number -q '.[0].number' 2>>$L)
  if [ -z "$PR" ]; then
    python3 "$G" check --claim "$LANE_CLAIM_FILE" --owner "$LANE_CLAIM_OWNER" >>$L 2>&1 || { echo "BLOCKER lease lost before PR create; branch $B@$HEAD left without PR" >>$L; exit 1; }
    type gh_throttle >/dev/null 2>&1 && gh_throttle >>$L 2>&1
    FILES=$($GH api repos/rupret007/$R/compare/$BASE...$B -q '[.files[].filename]|join(",")' 2>>$L)
    if python3 "$G" pre-pr --repo rupret007/$R --work-id $W --owner $OWNER --title "$N" --branch $B --files "$FILES" >>$L 2>&1; then
      PR=$($GH pr create -R rupret007/$R --draft --head $B --base $BASE --title "$N" --body "$PROV $M lane ($TIER) $N (NucBox). See commits. Do not merge before Karen gate." 2>>$L | grep -oE '[0-9]+$')
      [ -n "$PR" ] || { echo "BLOCKER pushed $B@$HEAD but gh pr create failed" >>$L; exit 1; }
    else
      echo "BLOCKER pushed $B@$HEAD but claim-gate pre-pr refused a new PR" >>$L; exit 1
    fi
  fi
  echo "RESULT pr=https://github.com/rupret007/$R/pull/$PR head=$HEAD $(date)" >>$L
  exit 0
fi
N=$1 R=$2 B=$3 BASE=$4 W=$5 WAIT=$6; L=$D/$N.log
. ${LANE_GUARD:-$HOME/bin/lane-guard.sh}
PROV=${LANE_PROVIDER:-cursor}; TIER=${LANE_TIER:-cheap}; M=${LANE_MODEL:-composer-2.5}; EFF=${LANE_EFFORT:-high}
[ "$TIER" = high ] && EFF=${LANE_EFFORT:-high}; [ "$TIER" = xhigh ] && EFF=${LANE_EFFORT:-xhigh}; [ "$TIER" = cheap ] && EFF=${LANE_EFFORT:-medium}
case " gpt-5.3-codex-high gemini-3.1-pro claude-sonnet-5-thinking-high " in *" $M "*) echo "LANE model $M blocked on Cursor until 10/21 -> composer-2.5" >>$L; M=composer-2.5;; esac
# v6.5: LANE_PROVIDER=codex -> Windows Codex on NucBox (never Cursor Ultra blocked models)
[ "$PROV" = codex ] && M=${CODEX_MODEL:-gpt-6-astra}
echo "LANE provider=$PROV tier=$TIER model=$M effort=$EFF" >>$L; printf "%s\t%s\tnuc-lane\t%s\t%s\n" "$(date +%F\ %T)" $N $M $TIER >> $D/provider-usage.tsv
[ -n "$WAIT" ] && while screen -ls | grep -q "\.$WAIT[[:space:]]"; do sleep 30; done
LANE_TAG=cursor-$N; [ "$PROV" = codex ] && LANE_TAG=codex-$N
rc=3
for i in 1 2 3; do
  python3 $G claim --repo rupret007/$R --work-id $W ${PRNUM:+--pr $PRNUM} --title "$N" --owner $OWNER --lane $LANE_TAG --ttl-min 300 --lease-s ${LANE_LEASE_S:-900} >$L.claim 2>&1; rc=$?
  cat $L.claim >>$L
  [ $rc = 3 ] || break
  [ $i -lt 3 ] && sleep $((15 * i * i))   # 15 s, 60 s: B8, was 6 x 300 s inside a counted slot
done
case $rc in 0|11) ;; *) echo "CLAIM rc=$rc, not starting" >>$L; exit 1;; esac
CF=$(python3 -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().strip().splitlines()[-1]).get("claim",""))' $L.claim 2>/dev/null)
[ -n "$CF" ] || { echo "BLOCKER claim file missing from claim-gate output; not starting" >>$L; exit 1; }
lane_preflight >>$L 2>&1 || { echo "PREFLIGHT FAILED, not starting" >>$L; python3 $G release --claim "$CF" --owner $OWNER --status FAILED >>$L 2>&1; exit 1; }
export NL_MODEL=$M NL_EFF=$EFF LANE_PROVIDER=$PROV LANE_TIER=$TIER LANE_LOG_DIR=$D CLAIM_GATE=$G NUC_SSH="$SSH" NUC_LANE_OWNER=$OWNER
export LANE_REMOTE_NAME=$N LANE_REMOTE_SSH="$SSH"
exec bash ${LANE_LEASE:-$D/lane-lease.sh} "$CF" $OWNER -- bash "$0" --inner "$N" "$R" "$B" "$BASE" "$W"

#!/bin/bash
# usage: nuc-lane.sh NAME REPO BRANCH BASE WORKID [WAIT_SCREEN] ; prompt at ~/lane-wt/logs/NAME.prompt
# v5: LANE_TIER=cheap|high (default cheap) and LANE_MODEL (default composer-2.5; e.g. gemini-3.1-pro, claude-sonnet-5-thinking-high, gpt-5.3-codex-high)
N=$1 R=$2 B=$3 BASE=$4 W=$5 WAIT=$6; L=~/lane-wt/logs/$N.log; G=~/Documents/bob-overnight-inject/bin/claim-gate.py
. $HOME/bin/lane-guard.sh
TIER=${LANE_TIER:-cheap}; M=${LANE_MODEL:-composer-2.5}; case " gpt-5.3-codex-high gemini-3.1-pro claude-sonnet-5-thinking-high " in *" $M "*) echo "LANE model $M blocked on Cursor until 10/21 -> composer-2.5" >>$L; M=composer-2.5;; esac; echo "LANE tier=$TIER model=$M" >>$L; printf "%s\t%s\tnuc-lane\t%s\t%s\n" "$(date +%F\ %T)" $N $M $TIER >> ~/lane-wt/logs/provider-usage.tsv
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=30 -i $HOME/.ssh/nuc_ed25519 -p 2222 rupret@nuc-wsl"
[ -n "$WAIT" ] && while screen -ls | grep -q "\.$WAIT[[:space:]]"; do sleep 30; done
for i in 1 2 3 4 5 6; do python3 $G claim --repo rupret007/$R --work-id $W ${PRNUM:+--pr $PRNUM} --title "$N" --owner grok-exec-games-1616 --lane cursor-$N --ttl-min 300 >>$L 2>&1; rc=$?; [ $rc = 3 ] && { sleep 300; continue; }; break; done
case $rc in 0|11) ;; *) echo "CLAIM rc=$rc, not starting" >>$L; exit;; esac
P=$(cat ~/lane-wt/logs/$N.prompt)
lane_preflight >>$L 2>&1 || { echo "PREFLIGHT FAILED, not starting" >>$L; exit 1; }
if $SSH true 2>/dev/null; then
  echo "HOST nucbox $(date)" >>$L
  $SSH "cat > ~/work/results/$N.prompt" < ~/lane-wt/logs/$N.prompt
  $SSH "bash -l ~/nuc-tools/lane-run.sh $N $R $B $BASE $M" >>$L 2>&1
else
  echo "HOST mini-fallback (nucbox unreachable) $(date)" >>$L
  cd ~/lane-wt; [ -d $N ] || git clone -q https://github.com/rupret007/$R.git $N; cd $N; git fetch -q origin
  git ls-remote --exit-code --heads origin $B >/dev/null && git checkout -q -B $B origin/$B || git checkout -q -B $B origin/$BASE
  mini_wait >>$L 2>&1 || { echo "MINI-GUARD refused fallback run" >>$L; exit 1; }
  ~/.local/bin/cursor-agent agent --model $M -f --trust -p "$P" >>$L 2>&1; echo "EXIT $?" >>$L
fi
gh_throttle >>$L 2>&1
HEAD=$(git ls-remote https://github.com/rupret007/$R.git refs/heads/$B | cut -f1)
[ -z "$HEAD" ] && { echo "NO BRANCH PUSHED" >>$L; exit; }
PR=$(gh pr list -R rupret007/$R --head $B --state open --json number -q '.[0].number')
if [ -z "$PR" ]; then
  gh_throttle >>$L 2>&1; FILES=$(gh api repos/rupret007/$R/compare/$BASE...$B -q '[.files[].filename]|join(",")')
  python3 $G pre-pr --repo rupret007/$R --work-id $W --owner grok-exec-games-1616 --title "$N" --branch $B --files "$FILES" >>$L 2>&1 && \
  PR=$(gh pr create -R rupret007/$R --draft --head $B --base $BASE --title "$N" --body "Cursor $M lane ($TIER) $N (NucBox). See commits. Do not merge before Karen gate." | grep -oE '[0-9]+$')
fi
echo "RESULT pr=$PR head=$HEAD $(date)" >>$L

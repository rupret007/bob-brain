#!/bin/bash
# lane-run-codex.sh NAME [EFFORT]
# NucBox Codex lane via Windows desktop CLI (existing ChatGPT sign-in).
# Shares flock slots + load gate with lane-run.sh / lane-run-q.sh (NUC_MAX_LANES, NUC_LOAD_MAX).
# Prompt at ~/work/results/NAME.prompt ; workdir ~/work/NAME
N=$1; EFF=${2:-high}; MAX=${NUC_MAX_LANES:-4}; LMAX=${NUC_LOAD_MAX:-12}
set -e
[ -x ~/nuc-tools/codex-win.sh ] || { echo "BLOCKER codex-win.sh missing"; exit 2; }
[ -f ~/work/results/$N.prompt ] || { echo "BLOCKER missing prompt ~/work/results/$N.prompt"; exit 2; }
mkdir -p ~/work/.slots ~/work/$N
got=
while [ -z "$got" ]; do
  for i in $(seq 1 $MAX); do
    exec 9>~/work/.slots/$i
    if flock -n 9; then got=$i; break; fi
    exec 9>&-
  done
  if [ -n "$got" ] && [ "$(cut -d" " -f1 /proc/loadavg | cut -d. -f1)" -ge "$LMAX" ]; then
    exec 9>&-; got=
  fi
  [ -z "$got" ] && sleep 30
done
echo "SLOT $got/$MAX provider=codex model=${CODEX_MODEL:-gpt-6-astra} effort=$EFF load=$(cut -d" " -f1 /proc/loadavg) $(date)"
cd ~/work/$N
set +e
# Match Mini fill.sh: effort override, skip-git-repo-check, prompt as arg, stdin closed.
# No -s: Windows Codex uses its signed-in desktop sandbox policy (do not touch config/auth).
~/nuc-tools/codex-win.sh exec \
  -c "model_reasoning_effort=\"$EFF\"" \
  --skip-git-repo-check \
  -C ~/work/$N \
  "$(cat ~/work/results/$N.prompt)" </dev/null
echo "EXIT $?"

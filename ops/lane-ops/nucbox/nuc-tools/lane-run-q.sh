#!/bin/bash
# lane-run-q.sh NAME MODEL : fill.sh v5 queue job on NucBox (prompt ~/work/results/NAME.prompt). Same slot cap + load gate as lane-run.sh.
N=$1; MODEL=${2:-composer-2.5}; MAX=${NUC_MAX_LANES:-4}; LMAX=${NUC_LOAD_MAX:-12}
. ~/.nvm/nvm.sh; [ -f ~/nuc-tools/pw-env.sh ] && . ~/nuc-tools/pw-env.sh
[ -x ~/.local/bin/cursor-agent ] || { echo "BLOCKER cursor-agent missing"; exit 2; }
mkdir -p ~/work/.slots ~/work/$N; got=
while [ -z "$got" ]; do
  for i in $(seq 1 $MAX); do exec 9>~/work/.slots/$i; if flock -n 9; then got=$i; break; fi; exec 9>&-; done
  if [ -n "$got" ] && [ "$(cut -d' ' -f1 /proc/loadavg | cut -d. -f1)" -ge "$LMAX" ]; then exec 9>&-; got=; fi
  [ -z "$got" ] && sleep 30
done
echo "SLOT $got/$MAX model=$MODEL load=$(cut -d' ' -f1 /proc/loadavg) $(date)"
cd ~/work/$N && ~/.local/bin/cursor-agent agent --model $MODEL -f --trust -p "$(cat ~/work/results/$N.prompt)"; echo "EXIT $?"

#!/bin/bash
# NucBox lane runner: lane-run.sh NAME REPO BRANCH BASE   (prompt at ~/work/results/NAME.prompt)
# Concurrency slots (flock) + load gate + Playwright libs for every child process.
N=$1 R=$2 B=$3 BASE=$4; MODEL=${5:-composer-2.5}; MAX=${NUC_MAX_LANES:-4}; LMAX=${NUC_LOAD_MAX:-12}
set -e; . ~/.nvm/nvm.sh; [ -f ~/nuc-tools/pw-env.sh ] && . ~/nuc-tools/pw-env.sh
command -v flock >/dev/null || { echo "PREFLIGHT FAIL no flock"; exit 2; }
[ -x ~/.local/bin/cursor-agent ] || { echo "PREFLIGHT FAIL cursor-agent missing"; exit 2; }
ls ~/.local/pwlibs/usr/lib/x86_64-linux-gnu/libnspr4.so >/dev/null || { echo "PREFLIGHT FAIL libnspr4"; exit 2; }
mkdir -p ~/work/.slots; got=
while [ -z "$got" ]; do
  for i in $(seq 1 $MAX); do exec 9>~/work/.slots/$i; if flock -n 9; then got=$i; break; fi; exec 9>&-; done
  if [ -n "$got" ] && [ "$(cut -d' ' -f1 /proc/loadavg | cut -d. -f1)" -ge "$LMAX" ]; then exec 9>&-; got=; fi
  [ -z "$got" ] && sleep 30
done
echo "SLOT $got/$MAX load=$(cut -d' ' -f1 /proc/loadavg) $(date)"
cd ~/work; [ -d $N ] || git clone -q https://github.com/rupret007/$R.git $N; cd $N; git fetch -q origin
if git ls-remote --exit-code --heads origin $B >/dev/null; then git checkout -q -B $B origin/$B; else git checkout -q -B $B origin/$BASE; fi
set +e; ~/.local/bin/cursor-agent agent --model $MODEL -f --trust -p "$(cat ~/work/results/$N.prompt)"; echo "EXIT $?"

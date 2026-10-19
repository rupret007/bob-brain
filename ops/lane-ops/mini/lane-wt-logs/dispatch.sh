#!/bin/zsh
# Max 2 active lanes; queue: resume turdanoid (paused), then amv. Load gate <14.
L=~/lane-wt/logs/dispatch.log
load(){ sysctl -n vm.loadavg | awk '{print $2}'; }
active(){ n=0; for s in lane-webjam lane-andrea lane-amv; do screen -ls | grep -q "\.$s" && n=$((n+1)); done; [[ -f ~/lane-wt/logs/turd.resumed ]] && screen -ls | grep -q lane-turdanoid && n=$((n+1)); echo $n; }
while true; do
  a=$(active); l=$(load)
  if (( a < 2 )) && (( ${l%.*} < 12 )); then
    if [[ ! -f ~/lane-wt/logs/turd.resumed || ! -f ~/lane-wt/logs/amv.started ]]; then
      # Legacy run.sh is a local Codex runner; neither resume nor launch it on the Mini.
      echo "$(date) MINI-CODEX REFUSED" >> $L
      exit 3
    fi
  fi
  screen -ls | grep -q "lane-" || { echo "$(date) drained" >> $L; exit 0; }
  sleep 60
done

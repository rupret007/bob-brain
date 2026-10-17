#!/bin/zsh
# Max 2 active lanes; queue: resume turdanoid (paused), then amv. Load gate <14.
L=~/lane-wt/logs/dispatch.log
load(){ sysctl -n vm.loadavg | awk '{print $2}'; }
active(){ n=0; for s in lane-webjam lane-andrea lane-amv; do screen -ls | grep -q "\.$s" && n=$((n+1)); done; [[ -f ~/lane-wt/logs/turd.resumed ]] && screen -ls | grep -q lane-turdanoid && n=$((n+1)); echo $n; }
while true; do
  a=$(active); l=$(load)
  if (( a < 2 )) && (( ${l%.*} < 12 )); then
    if [[ ! -f ~/lane-wt/logs/turd.resumed ]]; then pkill -CONT -f lane-wt/turdanoid; pkill -CONT -f "run.sh turdanoid"; for p in $(pgrep -f "codex exec.*turdanoid"); do kill -CONT -$(ps -o pgid= -p $p|tr -d ' '); done; touch ~/lane-wt/logs/turd.resumed; echo "$(date) resumed turdanoid load=$l" >> $L
    elif [[ ! -f ~/lane-wt/logs/amv.started ]]; then screen -dmS lane-amv ~/lane-wt/logs/run.sh amv-70 amv; touch ~/lane-wt/logs/amv.started; echo "$(date) started amv load=$l" >> $L
    fi
  fi
  screen -ls | grep -q "lane-" || { echo "$(date) drained" >> $L; exit 0; }
  sleep 60
done

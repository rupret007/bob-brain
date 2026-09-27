#!/usr/bin/env bash
# tick every 15 min; conductor every 2 h (8 ticks)
cd "$HOME/Documents/bob-overnight-inject" || exit 1
n=0
while true; do
  bash conductor/run-tick.sh
  if [ $((n % 8)) -eq 0 ]; then bash conductor/run-conductor.sh; fi
  n=$((n+1)); sleep 900
done

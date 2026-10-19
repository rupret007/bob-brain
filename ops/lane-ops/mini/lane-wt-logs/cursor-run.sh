#!/bin/zsh
# usage: cursor-run.sh <workdir> <job>   strongest local Cursor model (Jeff 2026-10-16)
M=${CURSOR_MODEL:-composer-2.5}   # Opus 5.5 Max + GPT-5.6 Sol Max hit Cursor usage limit 00:02 (resets 10/21); composer still included
cd $1 && ~/.local/bin/cursor-agent -p -f --trust --model $M --workspace $1 "$(cat ~/lane-wt/logs/$2.prompt)" > ~/lane-wt/logs/$2.log 2>&1
echo "EXIT $? model=$M $(date)" >> ~/lane-wt/logs/$2.log
grep -q -E '^(RESULT|BLOCKER)' ~/lane-wt/logs/$2.log || echo 'BLOCKER no RESULT line' >> ~/lane-wt/logs/$2.log

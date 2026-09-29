#!/bin/bash
# Web Bob autopilot: one builder (Cursor, fallback Codex) at a time; council each round; optional stop via ~/STOP-WEBBOB.
B=~/Documents/bob-overnight-inject; cd $B; LOG=$B/logs/wb-autopilot.log; mkdir -p logs conductor/locks
say(){ echo "$(date '+%F %T') $*" >> $LOG; }
exec 9>>"$B/conductor/locks/wb-autopilot.lock"
flock -n 9 || { say "another autopilot holds wb-autopilot.lock; exiting"; exit 0; }
wait_builders(){ while screen -ls | grep -qE 'svc-webchat-ready-r[0-9]'; do sleep 60; done; }
passes=0
last_n=$(ls conductor/reviews/WEBCHAT-READY-R*-RESULT.md 2>/dev/null | sed -E 's/.*R([0-9]+)-RESULT.*/\1/' | sort -n | tail -1)
n=$(( ${last_n:-0} + 1 ))
while [ ! -f ~/STOP-WEBBOB ]; do
  wait_builders
  last=$(ls -t conductor/reviews/WEBCHAT-READY-R*-RESULT.md | head -1)
  low=$(grep -E '^\|' "$last" | grep -oE '\*\*[0-9]+(\.[0-9])?\*\*' | tr -d '*' | awk '$1<9' | wc -l | tr -d ' ')
  say "latest=$last below9=$low next_round=$n"
  if [ "$low" = "0" ]; then passes=$((passes+1)); [ $passes -ge 2 ] && say "all>=9 twice; continuing: raise bar and find new improvements"; else passes=0; fi
  P="Read conductor/WEBCHAT-READY.md in full (every ADDED section) and $last. Round $n of Web Bob. FIRST do the iPhone-first redesign section before anything else. Start with a research pass on what exists today and write a design note (borrow, reject, why) per the Research-first section. Top priority: Web Bob better than Bob, and failover BOTH ways (Bob to Web Bob and back) with zero lost context, proved by a live drill run twice. Also build the detailed live dashboard section. Fix the lowest scores first. Get critiques from Gemini, MiniMax, and Claude via python3 conductor/services/council.py and resolve disagreements by council vote. Music: use only what we have (no MiniMax music API, no signups). Re-score numerically (0-10), run the e2e drill, and restart webchat safely (kill the PID on 127.0.0.1:8787, then run bash conductor/webchat/start.sh). Commit on the draft branch only. Never merge, never force-push, never use Grok. Write conductor/reviews/WEBCHAT-READY-R$n-RESULT.md with scores and SHAs."
  say "start R$n cursor"
  screen -dmS svc-webchat-ready-r$n bash -c "cd $B && perl -e 'alarm 7200; exec @ARGV' ~/.local/bin/cursor-agent -p \"\$0\" --output-format stream-json --trust -f > logs/svc-webchat-ready-r$n.log 2>&1 || (echo CURSOR_FAIL >> logs/svc-webchat-ready-r$n.log; cd conductor && perl -e 'alarm 7200; exec @ARGV' codex exec --dangerously-bypass-approvals-and-sandbox \"\$0\" >> ../logs/svc-webchat-ready-r$n.log 2>&1)" "$P"
  wait_builders
  n=$((n+1))
done

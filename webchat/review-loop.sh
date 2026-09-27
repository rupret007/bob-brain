#!/bin/bash
# Parallel Web Bob reviewers (Gemini, MiniMax, Claude, and Cursor through the council tool). No Grok. Every 15 minutes, when there are new commits.
cd ~/Documents/bob-overnight-inject
last=""
while true; do
  tip=$(git -C conductor log -1 --all --format=%h -- webchat 2>/dev/null)
  if [ -n "$tip" ] && [ "$tip" != "$last" ]; then
    out=reviews/webbob-council-$(date +%Y%m%dT%H%M)
    git -C conductor diff HEAD~3 -- webchat > /tmp/webbob-diff.txt 2>/dev/null || true
    cat conductor/WEBCHAT-READY.md /tmp/webbob-diff.txt > /tmp/webbob-ctx.txt
    perl -e 'alarm 900; exec @ARGV' python3 conductor/services/council.py --context /tmp/webbob-ctx.txt --out "$out" "Score Web Bob 0-10 on reliability, speed, mobile, Bob parity, architecture, and safety. List the top 5 concrete fixes to make it work as well as Bob. Be specific (file and change)." || true
    last=$tip
  fi
  sleep 900
done

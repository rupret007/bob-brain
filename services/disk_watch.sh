#!/bin/bash
# Disk monitor: every 5 min log free GB; warn <15GB, alert <8GB, safe-clean caches <5GB.
B=~/Documents/bob-overnight-inject; L=$B/logs/disk-watch.log; S=$B/conductor/state/DISK.txt
while true; do
  F=$(df -g ~ | tail -1 | awk '{print $4}'); TS=$(date '+%F %T')
  LVL=ok; [ "$F" -lt 15 ] && LVL=warn; [ "$F" -lt 8 ] && LVL=ALERT
  echo "$TS free=${F}GB level=$LVL" >> $L; echo "$TS free=${F}GB level=$LVL" > $S
  if [ "$LVL" != ok ]; then echo "- $TS DISK $LVL: ${F}GB free on mini" >> $B/conductor/state/INBOX.md; fi
  if [ "$F" -lt 5 ]; then rm -rf ~/Library/Caches/pip ~/Library/Caches/Homebrew ~/.npm/_cacache 2>/dev/null; find $B/logs -name '*.log' -size +200M -exec sh -c ': > "$1"' _ {} \; ; echo "$TS safe-clean ran" >> $L; fi
  sleep 300
done

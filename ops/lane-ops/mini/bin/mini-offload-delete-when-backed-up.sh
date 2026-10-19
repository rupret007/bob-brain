#!/bin/bash
# Waits (10-min checks, until 01:00 CT) for the Mini->NucBox backup to finish with last_backup: OK, then runs guarded delete.
# If a run ends not-OK, re-runs the (incremental, copy-only) backup once.
end=$(date -j -f "%Y-%m-%d %H:%M" "2026-10-17 01:00" +%s); retried=0
while :; do
  s=$(cat ~/lane-wt/logs/backup-status.txt 2>/dev/null); lk=$([ -d /tmp/nucbox-backup.lock ] && echo held || echo free)
  echo "$(date '+%H:%M %Z') status=[$s] lock=$lk"
  if [ "$lk" = free ] && [ -n "$s" ]; then
    case "$s" in
      "last_backup: OK"*) echo BACKUP_OK; exec ~/bin/mini-offload-delete.sh --delete;;
      *) if [ $retried = 0 ] && [ "$(date +%s)" -lt "$end" ]; then retried=1; rm -f ~/lane-wt/logs/backup-status.txt; echo "not OK - rerunning backup once"; nohup ~/bin/nucbox-backup.sh work >/dev/null 2>&1 & sleep 60; continue
         else echo "BACKUP_NOT_OK - deleting nothing"; exit 3; fi;;
    esac
  fi
  [ "$(date +%s)" -ge "$end" ] && { echo "TIMEOUT 01:00 - deleting nothing"; exit 4; }
  sleep 600
done

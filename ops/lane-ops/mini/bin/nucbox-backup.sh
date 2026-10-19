#!/bin/bash
# nucbox-backup.sh: nightly ONE-WAY, copy-only backup Mini -> NucBox WSL (~/backups/mini, stored on NucBox C:) over ssh.
# Never deletes at destination (no --delete). Usage: nucbox-backup.sh [work|drone|all]
# Drone footage (Hoser) is gated by BACKUP_DRONE=1 (off: NucBox C: has ~272 GB free vs ~420 GiB footage).
# Never copies ~/.cursor, ~/.codex, Claude auth, Keychain, Photos, iCloud, Messages, Apple Music library, node_modules, or secret/token files.
set -uo pipefail
mode="${1:-work}"; BACKUP_DRONE="${BACKUP_DRONE:-0}"
mkdir -p ~/lane-wt/logs
log=~/lane-wt/logs/backup-$(date +%Y%m%d-%H%M%S).log; status=~/lane-wt/logs/backup-status.txt
exec >>"$log" 2>&1
lock=/tmp/nucbox-backup.lock
if ! mkdir "$lock" 2>/dev/null; then echo "[backup] another run active, exiting"; exit 0; fi
trap 'rmdir "$lock"' EXIT
SSH="ssh -i $HOME/.ssh/nuc_ed25519 -p 2222 -o BatchMode=yes -o ConnectTimeout=15"
H=rupret@nuc-wsl; D=backups/mini
start=$(date '+%Y-%m-%d %H:%M %Z')
echo "[backup] start $start mode=$mode"
st(){ echo "last_backup: $1 | mode=$mode | started=$start | finished=$(date '+%Y-%m-%d %H:%M %Z') | log=$log" > "$status"; }
$SSH $H "mkdir -p ~/$D/work ~/$D/repos ~/$D/config ~/$D/drone" || { echo "[backup] NucBox unreachable"; st "FAILED (NucBox unreachable)"; exit 2; }
EX=(--exclude node_modules --exclude .cache --exclude tmp --exclude '.DS_Store' --exclude '*.env' --exclude '.env*' --exclude 'tokens*'
    --exclude '*token*' --exclude '*secret*' --exclude '*.pem' --exclude '*.key' --exclude 'id_rsa*' --exclude 'id_ed25519*' --exclude '.netrc'
    --exclude '.npmrc' --exclude 'credentials*' --exclude '.cursor' --exclude '.codex' --exclude '.claude' --exclude 'auth.json'
    --exclude test-results --exclude playwright-report --exclude .next --exclude .venv --exclude __pycache__ --exclude .turbo)
rc=0
run(){ local src="$1" dst="$2"; [ -e "$src" ] || return 0; echo "[backup] $src -> $dst"
  nice -n 15 rsync -a "${EX[@]}" -e "$SSH" "$src" "$H:$D/$dst/" || { echo "[backup] rsync failed for $src"; rc=1; }; }
if [ "$mode" = work ] || [ "$mode" = all ]; then
  for s in "$HOME/Documents/bob-overnight-inject" "$HOME/bin" "$HOME/Oui Cest Fou Music Video" "$HOME/Manic Music Video" "$HOME/Rad Dad Story of Us"; do run "$s" work; done
  run "$HOME/.config/bob-live" config
  # repos with unpushed commits or uncommitted changes (pushed work is already on GitHub)
  find "$HOME" "$HOME/Documents" "$HOME/lane-wt.noindex" "$HOME/.openclaw" -maxdepth 3 -name .git -not -path '*/node_modules/*' -not -path "$HOME/Music/*" \
     -not -path "$HOME/Library/*" -not -path "$HOME/.cursor/*" -not -path "$HOME/.codex/*" -not -path "$HOME/Documents/bob-overnight-inject/*" 2>/dev/null | sort -u |
  while read -r g; do r=$(dirname "$g")
    u=$(git -C "$r" log --branches --not --remotes --oneline 2>/dev/null | wc -l); c=$(git -C "$r" status --porcelain 2>/dev/null | wc -l)
    [ $((u+c)) -gt 0 ] || continue
    rel=${r#$HOME/}; parent=$(dirname "$rel"); $SSH $H "mkdir -p \"$D/repos/$parent\""
    echo "[backup] repo $rel (unpushed=$((u)) changed=$((c)))"
    nice -n 15 rsync -a "${EX[@]}" -e "$SSH" "$r" "$H:$D/repos/$parent/" || echo "[backup] rsync failed for $r"
  done
fi
if [ "$mode" = drone ] || [ "$mode" = all ]; then
  if [ "$BACKUP_DRONE" != 1 ]; then echo "[backup] drone skipped (BACKUP_DRONE=0: no destination with room)"
  elif [ ! -d /Volumes/Hoser ]; then echo "[backup] drone skipped (Hoser not mounted)"
  else for s in /Volumes/Hoser/ATOM_001 /Volumes/Hoser/Drone*; do echo "[backup] $s"; nice -n 15 rsync -a --exclude '.DS_Store' --exclude '._*' -e "$SSH" "$s" "$H:$D/drone/" || rc=1; done; fi
fi
echo "[backup] done $(date) rc=$rc"
[ $rc = 0 ] && st OK || st "PARTIAL (rc=$rc)"
exit $rc

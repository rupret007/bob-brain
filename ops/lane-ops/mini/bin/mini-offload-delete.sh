#!/bin/bash
# Delete Mini originals already copied+verified to Hoser (Jeff OK'd 2026-10-16 9:20 PM CT).
# Per item: Hoser mounted, checksum dry-run vs Hoser (only known skipped symlinks allowed), video also
# size-matched in NucBox backup, nothing open (lsof). Any failure = skip that item. rm -r never follows symlinks.
# Usage: mini-offload-delete.sh [--check|--delete]
set -uo pipefail
MODE="${1:---check}"
D=/Volumes/Hoser/MiniOffload
SSH="ssh -i $HOME/.ssh/nuc_ed25519 -p 2222 -o BatchMode=yes -o ConnectTimeout=15"; H=rupret@nuc-wsl
LOG="$HOME/lane-wt/logs/offload-delete-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
cd "$HOME" || exit 1
EXRE='(^|/)(node_modules|\.cache|tmp|test-results|playwright-report|\.next|\.venv|__pycache__|\.turbo|\.cursor|\.codex|\.claude)(/|$)|\.DS_Store$|\.env|token|secret|\.pem$|\.key$|id_rsa|id_ed25519|\.netrc$|\.npmrc$|(^|/)credentials|auth\.json$'
ITEMS=()
add(){ for p in "${@:2}"; do [ -e "$p" ] && ITEMS+=("$1|$p"); done; }
shopt -s nullglob
add video "Rad Dad Story of Us/output" "Rad Dad Story of Us/qa" "Manic Music Video/output" "Manic Music Video/qa"
add video "Oui Cest Fou Music Video/output/"Oui_Cest_Fou_R[123]_* "Oui Cest Fou Music Video/output/Oui_Cest_Fou_R4_1080p_pre-peakfix.mp4" "Oui Cest Fou Music Video/output/Oui_Cest_Fou_R4_Portrait_Chorus1_1080x1920_pre-peakfix.mp4"
for d in local-webjam-24h-1010 local-webjam-conflicts-1013 local-cursor-codex-leftovers-1005 local-cursor-polish-1006; do add archives "Documents/bob-overnight-inject/$d"; done
for d in andrea-webbob-20260929-040929 andrea-webbob-20260929-044257 andrea-webbob-primary-1002-20261002-143843 andrea-webbob-primary-1002-20261002-145801; do add webbob-releases ".andrea/webbob-releases/$d"; done
add webbob-releases ".andrea/quarantine"
add backups "Documents/ChatGPT/Storyland Fantasy/data/backups" "Documents/ChatGPT/Storyland Fantasy/data/"*-before.json "Documents/ChatGPT/Storyland Fantasy/data/"*-before.json.gz
add downloads "Downloads"
for it in "${ITEMS[@]}"; do case "$it" in *local-proj-max-1010*|*local-merge-1011*|*local-throughput-1012*|*storyland.sqlite*|*texting-intellect*|*wj-triage-1014*|*Hoser*|*ATOM*|*Drone*) echo "REFUSING $it"; exit 1;; esac
  case "$it" in *R4*) case "$it" in *_pre-peakfix.mp4) ;; *) echo "REFUSING R4 final $it"; exit 1;; esac;; esac; done
echo "== $(date '+%Y-%m-%d %H:%M %Z') mode=$MODE items=${#ITEMS[@]}"; echo "status: $(cat ~/lane-wt/logs/backup-status.txt 2>/dev/null)"
dfb=$(df -k / | awk 'NR==2{print $4}'); echo "df free before: $((dfb/1024)) MiB"
ok=0; skip=0; del=0
for it in "${ITEMS[@]}"; do
  cat="${it%%|*}"; src="${it#*|}"; par=$(dirname "$src"); dest="$D/$cat/$par/"
  why=""; nsl=0
  mount | grep -q ' on /Volumes/Hoser ' || why="Hoser not mounted"
  [ -z "$why" ] && { [ -e "$D/$cat/$par/$(basename "$src")" ] || why="no copy on Hoser"; }
  if [ -z "$why" ]; then
    out=$(rsync -rtc --modify-window=2 -n -i "$src" "$dest" 2>&1); rc=$?
    [ $rc -eq 0 ] || why="rsync dry-run rc=$rc"
    bad=""
    while IFS= read -r l; do
      [ -z "$l" ] && continue; case "$l" in cd*) continue;; esac
      if [[ "$l" == 'skipping non-regular file "'*'"' ]]; then p=${l#skipping non-regular file \"}; p=${p%\"}
        if [ -L "$par/$p" ]; then nsl=$((nsl+1)); continue; fi; fi
      bad+="$l"$'\n'
    done <<<"$out"
    [ -z "$bad" ] || why="${why:+$why; }checksum diffs: $(echo "$bad" | head -5 | tr '\n' '|')"
  fi
  if [ -z "$why" ] && [ "$cat" = video ]; then
    q=$(printf %q "$src")
    rl=$($SSH $H "cd ~/backups/mini/work 2>/dev/null && [ -e $q ] && find $q -type f -printf '%s %p\n' | LC_ALL=C sort" 2>/dev/null); rrc=$?
    ll=$(find "$src" -type f -exec stat -f '%z %N' {} + | LC_ALL=C sort)
    if [ $rrc -ne 0 ] || [ -z "$rl" ]; then why="not (yet) in NucBox backup"
    else d1=$(LC_ALL=C comm -23 <(echo "$ll") <(echo "$rl"))
      miss=$(echo "$d1" | grep -Ev "$EXRE" | grep .); exm=$(echo "$d1" | grep -Ec "$EXRE")
      [ -z "$miss" ] || why="NucBox size/file mismatch: $(echo "$miss" | head -3 | tr '\n' '|')"
      [ "$exm" -gt 0 ] && echo "   note: $exm backup-excluded files of $src are only on Hoser"; fi
  fi
  if [ -z "$why" ]; then
    if [ -d "$src" ]; then lo=$(lsof +D "$src" 2>/dev/null | tail -n +2); else lo=$(lsof "$src" 2>/dev/null | tail -n +2); fi
    [ -z "$lo" ] || why="open files: $(echo "$lo" | awk '{print $1}' | sort -u | tr '\n' ' ')"
  fi
  sz=$(du -sk "$src" | cut -f1)
  if [ -n "$why" ]; then echo "SKIP $src ($((sz/1024)) MiB): $why"; skip=$((skip+1)); continue; fi
  ok=$((ok+1))
  if [ "$MODE" = --delete ]; then
    if [ "$src" = Downloads ]; then
      find "$HOME/Downloads" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
      if [ -z "$(ls -A "$HOME/Downloads")" ]; then gone=1; else gone=0; fi
    else
      rm -rf "$src"
      if [ ! -e "$src" ] && [ ! -L "$src" ]; then gone=1; else gone=0; fi
    fi
    if [ $gone = 1 ]; then echo "DELETED $src ($((sz/1024)) MiB, $nsl symlinks removed, targets untouched)"; del=$((del+1)); else echo "DELETE INCOMPLETE $src"; fi
  else echo "OK-TO-DELETE $src ($((sz/1024)) MiB, $nsl symlinks)"; fi
done
dfa=$(df -k / | awk 'NR==2{print $4}')
echo "== passed=$ok deleted=$del skipped=$skip | df free before $((dfb/1024)) MiB after $((dfa/1024)) MiB | log $LOG"

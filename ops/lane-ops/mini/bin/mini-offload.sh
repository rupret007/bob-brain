#!/bin/bash
# Copy Group A (see mini-offload-plan) to the drive, verify by checksum, write report.
# NEVER deletes originals. Usage: mini-offload.sh /Volumes/Hoser/MiniOffload
set -uo pipefail
D="${1:?usage: mini-offload.sh /Volumes/Hoser/MiniOffload}"
VOL="/Volumes/$(echo "$D" | cut -d/ -f3)"
[ -d "$VOL" ] || { echo "Drive $VOL not mounted"; exit 1; }
cd "$HOME" || exit 1
REPORT="$HOME/mini-offload-report-$(date +%Y%m%d-%H%M).txt"
RS=(rsync -rt --modify-window=2)   # exFAT: no perms/owner/symlinks (openrsync)
# category|source (relative to ~)
ITEMS=()
add(){ for p in "${@:2}"; do [ -e "$p" ] && ITEMS+=("$1|$p"); done; }
add video "Rad Dad Story of Us/output" "Rad Dad Story of Us/qa" "Manic Music Video/output" "Manic Music Video/qa"
shopt -s nullglob
add video "Oui Cest Fou Music Video/output/"Oui_Cest_Fou_R[123]_* "Oui Cest Fou Music Video/output/"*_pre-peakfix.mp4
for d in local-webjam-24h-1010 local-webjam-conflicts-1013 local-cursor-codex-leftovers-1005 wj-triage-1014 local-cursor-polish-1006; do add archives "Documents/bob-overnight-inject/$d"; done
for d in andrea-webbob-20260929-040929 andrea-webbob-20260929-044257 andrea-webbob-primary-1002-20261002-143843 andrea-webbob-primary-1002-20261002-145801; do add webbob-releases ".andrea/webbob-releases/$d"; done
add webbob-releases ".andrea/quarantine"
add backups "Documents/ChatGPT/Storyland Fantasy/data/backups" "Documents/ChatGPT/Storyland Fantasy/data/"*-before.json "Documents/ChatGPT/Storyland Fantasy/data/"*-before.json.gz
add downloads "Downloads"
# never touch live items
for it in "${ITEMS[@]}"; do case "$it" in *local-proj-max-1010*|*local-merge-1011*|*local-throughput-1012*|*storyland.sqlite*|*texting-intellect*) echo "REFUSING live item $it"; exit 1;; esac; done
need=0; for it in "${ITEMS[@]}"; do k=$(du -sk "${it#*|}" | cut -f1); need=$((need+k)); done
free=$(df -k "$VOL" | awk 'NR==2{print $4}')
echo "Need $((need/1024)) MB (+10% margin), drive free $((free/1024)) MB" | tee "$REPORT"
[ "$free" -gt $((need*11/10)) ] || { echo "NOT ENOUGH SPACE - aborting" | tee -a "$REPORT"; exit 1; }
fail=0
for it in "${ITEMS[@]}"; do
  cat="${it%%|*}"; src="${it#*|}"
  if ps -axo command | grep -F -- "$src" | grep -v grep >/dev/null; then echo "SKIP (in use) $src" | tee -a "$REPORT"; fail=1; continue; fi
  if lsof +D "$src" 2>/dev/null | grep -q . ; then echo "SKIP (lsof open files) $src" | tee -a "$REPORT"; fail=1; continue; fi
  dest="$D/$cat/$(dirname "$src")"; mkdir -p "$dest"
  "${RS[@]}" "$src" "$dest/" || { echo "COPY FAILED $src" | tee -a "$REPORT"; fail=1; continue; }
  diff=$("${RS[@]}" -c --dry-run -i "$src" "$dest/" | grep -v '^cd' )
  if [ -z "$diff" ]; then echo "VERIFIED $src -> $dest" | tee -a "$REPORT"; else echo "MISMATCH $src" | tee -a "$REPORT"; echo "$diff" | head -20 >> "$REPORT"; fail=1; fi
done
find "${ITEMS[@]#*|}" -type l 2>/dev/null | sed 's/^/SYMLINK NOT COPIED (exFAT): /' | tee -a "$REPORT"
echo "Originals NOT deleted. Deleting needs Jeff's OK. Report: $REPORT"
[ $fail -eq 0 ] && echo ALL VERIFIED | tee -a "$REPORT"; exit $fail

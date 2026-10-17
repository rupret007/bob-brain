#!/bin/bash
# drift-check.sh [--no-nucbox]   (lane-ops v2; read-only)
# Compares every file in MANIFEST.tsv with its live copy on the Mini (local) and the NucBox (ssh).
# Prints OK / DRIFT / MISSING per file and exits 1 if anything differs, so a self-improvement round
# can flag hand edits that bypassed review. It never writes to a live path.
cd "$(dirname "$0")/.." || exit 2
NUC=1; [ "$1" = "--no-nucbox" ] && NUC=
SSH=(ssh -n -o BatchMode=yes -o ConnectTimeout=8 -i "$HOME/.ssh/nuc_ed25519" -p 2222 rupret@nuc-wsl)
sum(){ shasum -a 256 2>/dev/null | cut -c1-64 || sha256sum | cut -c1-64; }
bad=0
while IFS=$'\t' read -r repo host live; do
  [ "$repo" = repo_path ] && continue
  want=$(sum < "$repo")
  if [ "$host" = mini ]; then
    p=${live/#\~/$HOME}; [ -f "$p" ] || { echo "MISSING $host $live"; bad=1; continue; }
    have=$(sum < "$p")
  else
    [ -n "$NUC" ] || continue
    have=$("${SSH[@]}" "f=$live; [ -f \$f ] && sha256sum \$f | cut -c1-64" 2>/dev/null)
    [ -n "$have" ] || { echo "MISSING $host $live"; bad=1; continue; }
  fi
  if [ "$want" = "$have" ]; then echo "OK      $host $live"; else echo "DRIFT   $host $live"; bad=1; fi
done < MANIFEST.tsv
exit $bad

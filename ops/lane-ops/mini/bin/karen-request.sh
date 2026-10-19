#!/bin/bash
# karen-request.sh OWNER/REPO PR [--test-cmd CMD]   (lane-ops v3, arch-review-2 item 1: required pre-Karen self-gate)
# The ONLY way a lane or the conductor may ask Karen for a gate. Runs shared/pre-karen-check.py on the NucBox
# (tests and mutants run there, under the 3-slot test semaphore), stores the report on the Mini in
# coord/prekaren/<repo>__pr<N>__<head>.{log,json}, and prints one line:
#   KAREN_REQUEST_OK <repo>#<N> head=<sha> report=<path>     exit 0  -> send the Karen gate request now
#   KAREN_REQUEST_BLOCKED <repo>#<N> verdict=FAIL ...        exit 1  -> fix the FAILs first; do not ask Karen
#   KAREN_REQUEST_WAIT <repo>#<N> verdict=PENDING ...        exit 2  -> CI still running / could not run; retry later
# Karen keeps the final say: a PASS here only means the mechanical first round is done.
R=$1; PR=$2; shift 2 2>/dev/null
[ -n "$R" ] && [ -n "$PR" ] || { echo "usage: karen-request.sh OWNER/REPO PR [--test-cmd CMD]" >&2; exit 64; }
case $R in */*) ;; *) echo "repo must be OWNER/REPO" >&2; exit 64;; esac
case $PR in *[!0-9]*) echo "PR must be a number" >&2; exit 64;; esac
OUT=${PREKAREN_DIR:-$HOME/Documents/bob-overnight-inject/coord/prekaren}; mkdir -p "$OUT"
SSH=${NUC_SSH:-"ssh -o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=30 -i $HOME/.ssh/nuc_ed25519 -p 2222 rupret@nuc-wsl"}
CHECK=${PREKAREN_REMOTE:-"python3 ~/nuc-tools/pre-karen-check.py"}
GH=${GH:-gh}
head=$($GH pr view "$PR" -R "$R" --json headRefOid -q .headRefOid 2>/dev/null)
[ -n "$head" ] || { echo "KAREN_REQUEST_WAIT $R#$PR verdict=PENDING reason=cannot read PR head"; exit 2; }
base=$OUT/${R//\//__}__pr${PR}__${head:0:12}
extra=""; for a in "$@"; do extra+=" $(printf '%q' "$a")"; done
$SSH "$CHECK --repo $R --pr $PR --json /tmp/prekaren-\$\$.json$extra; rc=\$?; echo '---JSON---'; cat /tmp/prekaren-\$\$.json 2>/dev/null; rm -f /tmp/prekaren-\$\$.json; exit \$rc" </dev/null > "$base.raw" 2>&1
rc=$?
sed '/^---JSON---$/,$d' "$base.raw" > "$base.log"; sed '1,/^---JSON---$/d' "$base.raw" > "$base.json"; rm -f "$base.raw"
now=$($GH pr view "$PR" -R "$R" --json headRefOid -q .headRefOid 2>/dev/null)
if [ "$now" != "$head" ]; then echo "KAREN_REQUEST_WAIT $R#$PR verdict=PENDING reason=head moved ${head:0:12}->${now:0:12} during the check; rerun"; exit 2; fi
v=$(grep -oE '^PRE-KAREN RESULT [A-Z]+' "$base.log" | awk '{print $3}' | tail -1)
case "$rc:$v" in
  0:PASS) echo "KAREN_REQUEST_OK $R#$PR head=$head report=$base.log"; exit 0;;
  1:FAIL) echo "KAREN_REQUEST_BLOCKED $R#$PR verdict=FAIL head=${head:0:12} report=$base.log"; grep -E '^PRE-KAREN [a-z-]+ FAIL' "$base.log" | head -12; exit 1;;
  *) echo "KAREN_REQUEST_WAIT $R#$PR verdict=${v:-PENDING} rc=$rc head=${head:0:12} report=$base.log"; grep -E '^PRE-KAREN [a-z-]+ (FAIL|PENDING)' "$base.log" | head -8; exit 2;;
esac

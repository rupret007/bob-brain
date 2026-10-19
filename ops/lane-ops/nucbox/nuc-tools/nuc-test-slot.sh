#!/bin/bash
# nuc-test-slot.sh [--] CMD...   (lane-ops v3, arch-review-2 capacity item 7)
# Runs CMD while holding one of NUC_TEST_SLOTS (default 3) NucBox test slots, separate from the LLM lane slots.
# Overlapping npm ci / pytest / vitest runs (each up to `timeout 1500`) drove the NucBox to load 22 on 14 cores;
# LLM lanes mostly wait on the network, so tests are what need the cap. Waits up to NUC_TEST_SLOT_WAIT seconds
# (default 3600) for a free slot, then exits 75 without running CMD. Exit status is CMD's otherwise.
MAX=${NUC_TEST_SLOTS:-3}; WAIT=${NUC_TEST_SLOT_WAIT:-3600}; D=${NUC_TEST_SLOT_DIR:-$HOME/work/.test-slots}
[ "${1:-}" = -- ] && shift
[ $# -gt 0 ] || { echo "usage: nuc-test-slot.sh [--] CMD..." >&2; exit 2; }
command -v flock >/dev/null || { echo "BLOCKER flock missing" >&2; exit 2; }
mkdir -p "$D"; t0=$(date +%s); got=
while :; do
  for i in $(seq 1 "$MAX"); do
    exec 7>"$D/$i"
    if flock -n 7; then got=$i; break 2; fi
    exec 7>&-
  done
  [ $(( $(date +%s) - t0 )) -ge "$WAIT" ] && { echo "TEST-SLOT none free after ${WAIT}s (max $MAX)" >&2; exit 75; }
  sleep "${NUC_TEST_SLOT_POLL:-10}"
done
echo "TEST-SLOT $got/$MAX $(date +%T)" >&2
"$@" 7>&-
rc=$?
exit $rc

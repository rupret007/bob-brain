#!/bin/bash
# lane-lease.sh CLAIM_FILE OWNER -- CMD [ARGS...]   (lane-ops v2)
# Runs CMD while holding a claim-gate lease: renews the claim's heartbeat every LANE_LEASE_EVERY seconds
# (default 300) and releases the claim when CMD ends, however it ends (normal exit, error, SIGHUP from
# `screen -X quit`, SIGINT, SIGTERM). If this wrapper itself is killed with SIGKILL or the Mini reboots,
# renewals stop and claim-gate treats the claim as free once its lease_s (default 900 s) passes.
# Exit status is CMD's. Status written on release: DONE on exit 0, FAILED otherwise.
# With an empty CLAIM_FILE it just runs CMD (so callers without a claim keep working).
G=${CLAIM_GATE:-$HOME/Documents/bob-overnight-inject/bin/claim-gate.py}
EVERY=${LANE_LEASE_EVERY:-300}
C=$1; O=$2; shift 2
[ "$1" = "--" ] && shift
[ $# -gt 0 ] || { echo "usage: lane-lease.sh CLAIM_FILE OWNER -- CMD..." >&2; exit 2; }
if [ -z "$C" ]; then "$@"; exit $?; fi
if [ "$O" = "-" ]; then O=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("owner",""))' "$C" 2>/dev/null); fi
[ -n "$O" ] || { echo "lane-lease: no owner for $C; running without lease" >&2; "$@"; exit $?; }
rc=1; cpid=; rpid=; released=
release(){
  [ -n "$released" ] && return; released=1
  [ -n "$rpid" ] && kill "$rpid" 2>/dev/null
  st=DONE; [ "$rc" = 0 ] || st=FAILED
  python3 "$G" release --claim "$C" --owner "$O" --status "$st" >/dev/null 2>&1 \
    || echo "lane-lease: release of $C failed (lease will lapse on its own)" >&2
}
on_signal(){ [ -n "$cpid" ] && kill -TERM "$cpid" 2>/dev/null; rc=143; release; exit 143; }
trap on_signal HUP INT TERM
trap release EXIT
( while sleep "$EVERY"; do
    python3 "$G" renew --claim "$C" --owner "$O" >/dev/null 2>&1 || { echo "lane-lease: renew failed for $C" >&2; exit 0; }
  done ) &
rpid=$!
"$@" &
cpid=$!
wait "$cpid"; rc=$?
exit $rc

#!/bin/bash
# lane-lease.sh CLAIM_FILE OWNER -- CMD [ARGS...]   (lane-ops v2, v3 fixes from arch-review-2 B2/B3)
# Runs CMD while holding a claim-gate lease: renews the claim's heartbeat every LANE_LEASE_EVERY seconds
# (default 300) and releases the claim when CMD ends, however it ends (normal exit, error, SIGHUP from
# `screen -X quit`, SIGINT, SIGTERM). If this wrapper itself is killed with SIGKILL or the Mini reboots,
# renewals stop and claim-gate treats the claim as free once its lease_s (default 900 s) passes.
# Exit status is CMD's. Status written on release: DONE on exit 0, FAILED otherwise.
# With an empty CLAIM_FILE it just runs CMD (so callers without a claim keep working).
#
# v3 (B2): a renew that keeps failing STOPS the lane. It used to `exit 0` quietly, so the lease lapsed while the
# agent kept working and pushing. The renew is retried LANE_RENEW_RETRIES times (default 2, 30 s apart) for a
# transient lock/disk hiccup, then CMD is sent SIGTERM, the wrapper exits 75 and the claim is released FAILED.
# CMD sees LANE_CLAIM_FILE / LANE_CLAIM_OWNER so it can fence with `claim-gate.py check` before a push.
# v3 (B3): with LANE_REMOTE_NAME + LANE_REMOTE_SSH set (NucBox lanes), every successful renew also refreshes the
# remote lane's heartbeat (`lane-supervise.sh beat NAME`), and every exit path stops the remote process group
# (`lane-supervise.sh stop NAME`), so an ssh drop or a Mini kill can no longer leave a second writer on the branch.
G=${CLAIM_GATE:-$HOME/Documents/bob-overnight-inject/bin/claim-gate.py}
EVERY=${LANE_LEASE_EVERY:-300}
RETRIES=${LANE_RENEW_RETRIES:-2}
RETRY_SLEEP=${LANE_RENEW_RETRY_SLEEP:-30}
C=$1; O=$2; shift 2
[ "$1" = "--" ] && shift
[ $# -gt 0 ] || { echo "usage: lane-lease.sh CLAIM_FILE OWNER -- CMD..." >&2; exit 2; }
if [ -z "$C" ]; then "$@"; exit $?; fi
if [ "$O" = "-" ]; then O=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("owner",""))' "$C" 2>/dev/null); fi
[ -n "$O" ] || { echo "lane-lease: no owner for $C; running without lease" >&2; "$@"; exit $?; }
export LANE_CLAIM_FILE="$C" LANE_CLAIM_OWNER="$O"
remote(){ # remote ACTION : no-op unless this is a NucBox lane
  [ -n "${LANE_REMOTE_NAME:-}" ] && [ -n "${LANE_REMOTE_SSH:-}" ] || return 0
  ${LANE_REMOTE_SSH} "bash -l ~/nuc-tools/lane-supervise.sh $1 $LANE_REMOTE_NAME" </dev/null >/dev/null 2>&1
}
rc=1; cpid=; rpid=; released=; lost=
release(){
  [ -n "$released" ] && return; released=1
  [ -n "$rpid" ] && { pkill -TERM -P "$rpid" 2>/dev/null; kill "$rpid" 2>/dev/null; }   # and its sleep, so no orphan holds our stdout
  remote stop
  st=DONE; [ "$rc" = 0 ] || st=FAILED
  python3 "$G" release --claim "$C" --owner "$O" --status "$st" >/dev/null 2>&1 \
    || echo "lane-lease: release of $C refused or failed (lease lapsed or claim-gate down; it lapses on its own)" >&2
}
stop_child(){ [ -n "$cpid" ] && { kill -TERM "$cpid" 2>/dev/null; pkill -TERM -P "$cpid" 2>/dev/null; }; }
on_signal(){ stop_child; rc=143; release; exit 143; }
on_lost(){ echo "lane-lease: lease for $C lost (renew failed ${RETRIES}x); stopping the lane" >&2; lost=1; stop_child; rc=75; release; exit 75; }
trap on_signal HUP INT TERM
trap on_lost USR1
trap release EXIT
WRAPPER=$$
( trap - HUP INT TERM USR1 EXIT
  while sleep "$EVERY"; do
    n=0
    until python3 "$G" renew --claim "$C" --owner "$O" >/dev/null 2>&1; do
      n=$((n+1))
      if [ "$n" -gt "$RETRIES" ]; then kill -USR1 "$WRAPPER" 2>/dev/null; exit 0; fi
      echo "lane-lease: renew failed for $C (try $n/$RETRIES)" >&2
      sleep "$RETRY_SLEEP"
    done
    remote beat
  done ) &
rpid=$!
"$@" &
cpid=$!
while :; do
  wait "$cpid"; rc=$?
  # wait returns early (>128) when a trapped signal arrives; the trap handlers exit, so loop only if CMD lives on
  kill -0 "$cpid" 2>/dev/null || break
done
exit $rc

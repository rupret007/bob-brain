#!/bin/bash
# lane-lease.sh CLAIM_FILE OWNER -- CMD [ARGS...]   (lane-ops v2, v3 fixes from arch-review-2 B2/B3)
# Runs CMD while holding a claim-gate lease: renews the claim's heartbeat every LANE_LEASE_EVERY seconds
# (default 300) and releases the claim when CMD ends, however it ends (normal exit, error, SIGHUP from
# `screen -X quit`, SIGINT, SIGTERM). If the Mini reboots, renewals stop and claim-gate treats the claim as free
# once its lease_s (default 900 s) passes.
# v4 (Karen #151 N1): the renewer is a WATCHDOG, not a free-running loop. It runs in its own process group, polls
# every LANE_WATCH_POLL s (default 2) that this wrapper is still its parent, and renews only then. If the wrapper is
# SIGKILLed (or its whole process group is), the watchdog stops CMD's process group, releases the claim FAILED and
# exits, so neither the lease nor the lane command is orphaned. (It used to keep renewing forever after kill -9.)
# v4 (N2): CMD runs in its own process group; every stop (HUP/INT/TERM, lost lease, watchdog) signals the WHOLE
# group (grandchildren included), TERM first, then KILL after LANE_KILL_GRACE s (default 10).
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
POLL=${LANE_WATCH_POLL:-2}
GRACE=${LANE_KILL_GRACE:-10}
killgroup(){ # killgroup PID : TERM the process group led by PID (and PID itself), KILL it after GRACE s
  local p=$1 i=0
  [ -n "$p" ] || return 0
  kill -TERM -- "-$p" 2>/dev/null; kill -TERM "$p" 2>/dev/null
  while kill -0 -- "-$p" 2>/dev/null && [ "$i" -lt "$GRACE" ]; do sleep 1; i=$((i+1)); done
  kill -KILL -- "-$p" 2>/dev/null
  return 0
}
release(){
  [ -n "$released" ] && return; released=1
  [ -n "$rpid" ] && { kill -TERM -- "-$rpid" 2>/dev/null; kill -TERM "$rpid" 2>/dev/null; }
  remote stop
  st=DONE; [ "$rc" = 0 ] || st=FAILED
  python3 "$G" release --claim "$C" --owner "$O" --status "$st" >/dev/null 2>&1 \
    || echo "lane-lease: release of $C refused or failed (lease lapsed or claim-gate down; it lapses on its own)" >&2
}
stop_child(){ killgroup "$cpid"; }
on_signal(){ stop_child; rc=143; release; exit 143; }
on_lost(){ echo "lane-lease: lease for $C lost (renew failed ${RETRIES}x); stopping the lane" >&2; lost=1; stop_child; rc=75; release; exit 75; }
trap on_signal HUP INT TERM
trap on_lost USR1
trap release EXIT
WRAPPER=$$
# N2: job control gives CMD (and the watchdog) their own process groups, so a group signal reaches grandchildren.
set -m
"$@" &
cpid=$!
# N1 watchdog (own process group, so a kill of the wrapper's group does not take it down with the wrapper)
( set +m   # inside the watchdog its own sleeps/renews stay in its group, so one group signal stops it all
  trap - HUP INT TERM USR1 EXIT
  trap 'exit 0' TERM
  nap(){ sleep "$1" & wait $!; }   # background sleep: a TERM lands at once and prints no job noise
  me=$(exec sh -c 'echo $PPID')
  alive(){ [ "$(ps -o ppid= -p "$me" 2>/dev/null | tr -d ' ')" = "$WRAPPER" ]; }
  orphaned(){ # the wrapper died without releasing (SIGKILL): stop the lane, release, leave
    echo "lane-lease: wrapper $WRAPPER died; stopping lane $cpid and releasing $C" >&2
    killgroup "$cpid"; remote stop
    python3 "$G" release --claim "$C" --owner "$O" --status FAILED >/dev/null 2>&1
    exit 0
  }
  waited=0
  while :; do
    nap "$POLL"; waited=$((waited+POLL))
    alive || orphaned
    [ "$waited" -ge "$EVERY" ] || continue
    waited=0
    n=0
    until python3 "$G" renew --claim "$C" --owner "$O" >/dev/null 2>&1; do
      n=$((n+1))
      alive || orphaned
      if [ "$n" -gt "$RETRIES" ]; then kill -USR1 "$WRAPPER" 2>/dev/null; exit 0; fi
      echo "lane-lease: renew failed for $C (try $n/$RETRIES)" >&2
      nap "$RETRY_SLEEP"
    done
    alive || orphaned
    remote beat
  done ) &
rpid=$!
disown "$rpid" 2>/dev/null   # no job-status noise; release()/watchdog still signal it by pid
set +m
[ -n "${LANE_LEASE_PIDFILE:-}" ] && echo "$cpid $rpid" > "$LANE_LEASE_PIDFILE"
while :; do
  wait "$cpid"; rc=$?
  # wait returns early (>128) when a trapped signal arrives; the trap handlers exit, so loop only if CMD lives on
  kill -0 "$cpid" 2>/dev/null || break
done
exit $rc

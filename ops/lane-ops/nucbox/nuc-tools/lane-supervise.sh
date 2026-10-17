#!/bin/bash
# lane-supervise.sh run NAME [LEASE_S] -- CMD...  |  beat NAME  |  stop NAME  |  ok NAME     (lane-ops v3, arch-review-2 B3)
# NucBox-side supervision for lanes the Mini starts over ssh. Before v3 the Mini ran `ssh nuc "bash -l lane-run*.sh"`
# with no remote supervision: when ssh dropped (Tailscale blip) or the Mini died, the Mini released the claim but the
# NucBox agent kept running and pushing, so two writers could share one branch.
#   run   starts CMD in its own session (setsid), records its process group in ~/work/.lanes/NAME.pgid, and kills the
#         whole group when (a) `stop NAME` is called, (b) the heartbeat file is older than LEASE_S (default 900 s;
#         the Mini's lane-lease.sh refreshes it on every successful renew), or (c) this ssh session goes away
#         (SIGHUP/SIGTERM/SIGPIPE). Exit status is CMD's (143 when it had to be stopped).
#   beat  refreshes NAME's heartbeat (refused once NAME was stopped).
#   stop  marks NAME stopped and kills its process group (TERM, then KILL after LANE_KILL_GRACE s).
#   ok    exit 0 only while NAME is running, not stopped and its heartbeat is fresh: the pre-push fence.
# CMD runs with LANE_NAME=NAME and core.hooksPath=lane-hooks/ (via GIT_CONFIG_* env), so every push it makes is
# fenced and policy-checked by lane-hooks/pre-push. (Windows codex.exe runs Windows git, which does not see WSL env;
# its pushes are still covered by the Mini-side fence in nuc-lane.sh and by pre-karen-check.)
D=${LANE_SUPERVISE_DIR:-$HOME/work/.lanes}; mkdir -p "$D"
CHECK=${LANE_SUPERVISE_CHECK:-15}; GRACE=${LANE_KILL_GRACE:-10}
act=$1; N=$2
[ -n "$act" ] && [ -n "$N" ] || { echo "usage: lane-supervise.sh run|beat|stop|ok NAME ..." >&2; exit 2; }
case $N in *[!A-Za-z0-9._-]*) echo "lane-supervise: bad name $N" >&2; exit 2;; esac
B=$D/$N.beat; S=$D/$N.stop; PG=$D/$N.pgid; LS=$D/$N.lease
age(){ [ -f "$1" ] || { echo 999999; return; }; echo $(( $(date +%s) - $(stat -c %Y "$1" 2>/dev/null || stat -f %m "$1") )); }
killgrp(){ local g; g=$(cat "$PG" 2>/dev/null); [ -n "$g" ] || return 0
  kill -TERM -- "-$g" 2>/dev/null; for _ in $(seq 1 "$GRACE"); do kill -0 -- "-$g" 2>/dev/null || return 0; sleep 1; done
  kill -KILL -- "-$g" 2>/dev/null; return 0; }
case $act in
  beat) [ -f "$S" ] && { echo "lane-supervise: $N was stopped" >&2; exit 3; }; touch "$B"; exit 0;;
  stop) touch "$S"; killgrp; exit 0;;
  ok)   [ -f "$S" ] && { echo "FENCE $N stopped"; exit 3; }
        [ -f "$PG" ] && kill -0 -- "-$(cat "$PG")" 2>/dev/null || { echo "FENCE $N not running under lane-supervise"; exit 3; }
        l=$(cat "$LS" 2>/dev/null || echo 900); [ "$(age "$B")" -le "$l" ] || { echo "FENCE $N heartbeat stale (>$l s)"; exit 3; }
        exit 0;;
  run)  shift 2; L=900; case ${1:-} in ''|--) ;; *) L=$1; shift;; esac; [ "${1:-}" = -- ] && shift
        [ $# -gt 0 ] || { echo "usage: lane-supervise.sh run NAME [LEASE_S] -- CMD..." >&2; exit 2; }
        rm -f "$S"; touch "$B"; echo "$L" > "$LS"
        command -v setsid >/dev/null || { echo "BLOCKER setsid missing" >&2; exit 2; }
        export LANE_NAME=$N
        # B6/B2: every git push inside this lane goes through lane-hooks/pre-push (fence + test-weakening policy),
        # whatever agent runs git. Env-level config, so no repo or global git config is changed.
        H=${LANE_HOOKS_DIR:-$(cd "$(dirname "$0")" && pwd -P)/lane-hooks}
        if [ -d "$H" ]; then i=${GIT_CONFIG_COUNT:-0}; export "GIT_CONFIG_KEY_$i=core.hooksPath" "GIT_CONFIG_VALUE_$i=$H" "GIT_CONFIG_COUNT=$((i+1))"; fi
        setsid "$@" & cpid=$!
        echo "$cpid" > "$PG"     # setsid makes the child its own process-group leader: pgid == pid
        why=
        trap 'why=ssh-gone; killgrp' HUP TERM INT PIPE
        while kill -0 "$cpid" 2>/dev/null; do
          if [ -f "$S" ]; then why=stopped; killgrp; break; fi
          if [ "$(age "$B")" -gt "$L" ]; then why="heartbeat stale >${L}s (lease lost)"; killgrp; break; fi
          sleep "$CHECK" & wait $! 2>/dev/null
        done
        wait "$cpid" 2>/dev/null; rc=$?
        [ -n "$why" ] && { echo "LANE-SUPERVISE stopped $N: $why"; rc=143; touch "$S"; }
        rm -f "$PG"; exit $rc;;
  *) echo "usage: lane-supervise.sh run|beat|stop|ok NAME ..." >&2; exit 2;;
esac

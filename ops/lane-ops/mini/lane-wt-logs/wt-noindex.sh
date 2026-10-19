#!/bin/bash
# selfimprove 10/16 22:10 CT: move proj-max worktrees under a .noindex path so Spotlight (mds_stores ~190% CPU, Mini load 24) stops indexing worktree churn.
# Acts only when no proj-max project lock is held and nothing has files open under wt. Gives up after 60 min.
# REVERT: rm ~/Documents/proj-max/wt && mv ~/Documents/proj-max/wt.noindex ~/Documents/proj-max/wt && cp $D/worker.sh.bak-wtnoindex $D/worker.sh
D=/Users/jeffstory/Documents/bob-overnight-inject/local-proj-max-1010; P=/Users/jeffstory/Documents/proj-max
log(){ echo "[$(date '+%F %T %Z')] wt-noindex $*" >> $D/driver.status; echo "- $(date +%H:%M) wt-noindex: $*" >> /Users/jeffstory/lane-wt/logs/selfimprove-rounds.md; }
busy(){ ls $D/locks/*/owner >/dev/null 2>&1 && return 0; [ -n "$(lsof +D $P/wt 2>/dev/null | tail -n +2)" ]; }
[ -L $P/wt ] && { log "already a symlink; nothing to do"; exit 0; }
end=$(( $(date +%s) + 3600 ))
while [ $(date +%s) -lt $end ]; do
  if ! busy; then
    sed 's#; W=/Users/jeffstory/Documents/proj-max/wt$#; W=/Users/jeffstory/Documents/proj-max/wt.noindex#' $D/worker.sh > $D/worker.sh.new
    n=$(diff $D/worker.sh $D/worker.sh.new | grep -c '^[<>]')
    [ "$n" = 2 ] || { log "worker.sh W line not found as expected (diff lines=$n); aborting, no change"; rm -f $D/worker.sh.new; exit 1; }
    cp -p $D/worker.sh $D/worker.sh.bak-wtnoindex; chmod --reference=$D/worker.sh $D/worker.sh.new 2>/dev/null || chmod 755 $D/worker.sh.new
    for s in $(screen -ls | grep -oE '[0-9]+\.grok-proj-max-w[0-9]+'); do screen -S $s -X quit; done; rm -f $D/locks/_heavy/owner.w* 2>/dev/null
    sleep 2
    if busy; then log "became busy during switch; restoring and retrying"; rm -f $D/worker.sh.new; sleep 30; continue; fi
    mv $D/worker.sh.new $D/worker.sh && mv $P/wt $P/wt.noindex && ln -s wt.noindex $P/wt && log "DONE: wt -> wt.noindex symlink, worker.sh W now wt.noindex, workers quit between items for keeper relaunch" && exit 0
    log "mv failed; check $P"; exit 1
  fi
  sleep 30
done
log "gave up after 60 min (proj-max wt never idle); no change"

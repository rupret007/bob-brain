#!/bin/zsh
# lane-ops v3 (arch-review-2): queue changes go through fill-queue.py (one lock, atomic rewrite; B5) and a refused
#   lease DEFERS the job instead of dropping it; Codex is NucBox-only (no Mini fallback at launch; item 10);
#   NucBox lanes run under nuc-tools/lane-supervise.sh with lane-lease.sh beating/stopping them (B2/B3).
# v6.5 (22:22 CT 10/16): Codex can run on NucBox (Windows CLI gpt-6-astra); CODEX_HOST=auto prefers Nuc when nuc_codex_ok; TGT_codex unchanged
# v5.3 (17:58 CT 10/16): high/xhigh -> Codex; Codex refused -> Cursor composer-2.5 fallback; never gpt-5.3-codex-high/gemini/claude via Cursor (usage limit until 10/21)
# v5.2 (17:40 CT 10/16): gemini -> gemini-lane.sh (direct Google API); claude -> claude -p on Mini (TGT 1, mini_ok, Karen reserve)
# Lane refill v5 (17:25 CT 10/16): provider/tier routing via lane-route.conf; see MAXPUSH notes.
# Lane refill v4 (Jeff 2026-10-16): continuous loop — never sit idle after drain.
# - claim-gate before start; skip repos/PRs Lane Dispatcher holds (fill-lease.py)
# - one start at a time, >=180s apart, only when 5-min load <14
# - if 5-min load >20 for 10 min, cap Codex at 4
# - Disk guard: hold when free <12GiB or fill.pause present
# - When queue pending < FILL_LOW_WATER (default 2), refill from open draft PRs + issues
#   via fill-autoqueue.py (priority: Web Bob, WebJam, AdoptIQ, StoryBoard, band sites…)
# - Each loop: fill-nw-guard.py — if NW.override=0 with no reason in NW-CHANGES.md, ALERT + restore ≥2
L=~/lane-wt/logs/dispatch.log
MAX=6
hot=0
cd ~/lane-wt/logs
LEASE=~/lane-wt/logs/fill-lease.py
AUTO=~/lane-wt/logs/fill-autoqueue.py
NWGUARD=~/lane-wt/logs/fill-nw-guard.py
LOW=${FILL_LOW_WATER:-6}   # v6: keep queue deep for 8 gemini lanes
IDLE_SLEEP=${FILL_IDLE_SLEEP:-120}
QFILE=~/lane-wt/logs/fill.queue
FQ=~/lane-wt/logs/fill-queue.py
q_ready(){ FILL_QUEUE=$QFILE python3 $FQ ready 2>>$L; }
q_remove(){ FILL_QUEUE=$QFILE python3 $FQ remove "$@" 2>>$L || echo "$(date) fill-queue remove $* failed" >> $L; }
q_defer(){ local v; v=$(FILL_QUEUE=$QFILE python3 $FQ defer "$@" 2>>$L); echo "$(date) fill $v (${FILL_DEFER_S:-600}s)" >> $L; }
. $HOME/bin/lane-guard.sh
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=30 -i $HOME/.ssh/nuc_ed25519 -p 2222 rupret@nuc-wsl"
. ~/lane-wt/logs/lane-route.sh

freeg(){ df -k / | awk "NR==2{printf \"%d\",\$4/1048576}"; }
l5(){ sysctl -n vm.loadavg | awk '{printf "%d",$3}'; }
nc(){ ps -Ao comm,args | awk '$1 ~ /codex$/ && / exec /' | wc -l | tr -d ' '; }
is_active(){ screen -ls 2>/dev/null | grep -qE "lane-(q|codex|codex-nuc|cursor|gemini|claude|minimax)-$1[[:space:]]"; }

PF=~/lane-wt/logs/.fill.pid   # v6.1 singleton: orphaned loops caused double starts
# lane-ops v2: atomic singleton. The pidfile check above was check-then-write, so two loops started together both won
# (5 loops ran at once on 10/16). zsystem flock holds an OS lock for the life of this shell; the kernel drops it when
# the loop dies (no stale lock), and zsh closes the fd on exec so screen children never inherit it.
zmodload zsh/system || { echo "$(date) fill: zsh/system unavailable; refusing to start without a lock" >> $L; exit 1; }
FILL_LOCK=${FILL_LOCK:-~/lane-wt/logs/.fill.lock}; : >> $FILL_LOCK
if ! zsystem flock -t 0 -f FILL_LOCK_FD $FILL_LOCK 2>/dev/null; then echo "$(date) fill: another loop holds $FILL_LOCK (pid $(cat $PF 2>/dev/null)); exit" >> $L; exit 0; fi
echo $$ > $PF
echo "$(date) fill v5 start (continuous; low-water=$LOW)" >> $L

while true; do
  . ~/lane-wt/logs/lane-route.sh      # v6.5: re-read helpers+conf every loop (CODEX_HOST, nuc_codex_ok)
  python3 "$NWGUARD" >/dev/null 2>>$L || echo "$(date) fill-nw-guard failed rc=$?" >> $L

  f=$(freeg)
  if (( f < 12 )) || [[ -f ~/lane-wt/logs/fill.pause ]]; then
    echo "$(date) disk guard: ${f}GiB free (<12) or fill.pause -> hold" >> $L
    sleep 300
    continue
  fi

  [[ -f $QFILE ]] || touch $QFILE
  pending=()
  for j in ${=$(q_ready)}; do
    is_active $j && continue
    (( ${pending[(Ie)$j]} )) && continue   # v6.1 dedupe
    pending+=($j)
  done

  if (( ${#pending[@]} < LOW )); then
    echo "$(date) fill queue low (${#pending[@]}<$LOW) -> autoqueue" >> $L
    python3 "$AUTO" >/dev/null 2>>$L || echo "$(date) fill-autoqueue failed rc=$?" >> $L
    [[ -f ~/lane-wt/logs/gemini.pause ]] || python3 ~/lane-wt/logs/gemini-feed.py 6 >> $L 2>&1   # v6: Gemini pre-review per new PR head
    pending=()
    for j in ${=$(q_ready)}; do
      is_active $j && continue
      (( ${pending[(Ie)$j]} )) && continue   # v6.1 dedupe
      pending+=($j)
    done
  fi

  if (( ${#pending[@]} == 0 )); then
    echo "$(date) fill idle: no pending jobs after refill; sleep ${IDLE_SLEEP}s" >> $L
    sleep $IDLE_SLEEP
    continue
  fi

  # v5 provider-aware pick: first pending job whose provider is under target and gated OK
  j=; prov=; tier=
  for c in $pending; do
    p=$(job_provider $c); t=$(job_tier $c)
    # v5.3 (until Cursor reset 10/21): high/xhigh always route to Codex; if Codex is refused, fall back to Cursor composer now (no waiting)
    [[ $t == high || $t == xhigh ]] && [[ $p != minimax ]] && p=codex
    if [[ $p == codex ]] && ! codex_start_ok $t; then
      [[ ${CODEX_REFUSED_FALLBACK:-cursor} == cursor ]] || continue
      echo "$(date) fill codex refused for $c (tier=$t host=${CODEX_HOST:-auto} ${MINI_STATE:-}) -> cursor $CURSOR_MODEL fallback" >> $L
      p=cursor
    fi
    eval "tg=\${TGT_$p:-0}"
    (( $(running $p) < tg )) || continue
    case $p in
      codex) ;;
      cursor) nuc_ok || continue;;
      gemini) gemini_ok || continue;;   # v6: API on Mini (light), tests on NucBox; cursor fallback still nuc-capped in lane-run-q
      claude) karen_busy && continue; mini_ok || continue;;   # v5.2: claude -p on Mini, max 1, Karen reserve
      minimax) (( $(mm_today) < MINIMAX_DAILY_CALLS )) || continue;;
    esac
    j=$c; prov=$p; tier=$t; break
  done
  if [[ -z $j ]]; then sleep 60; continue; fi

  if [[ ! -f ~/lane-wt/logs/q-$j.prompt ]]; then
    echo "$(date) fill SKIP $j (no prompt)" >> $L
    q_remove $j
    continue
  fi

  if is_active $j || awk -v j="$j" -v t=$(( $(date +%s) - 600 )) '$2==j && $1>t{f=1} END{exit !f}' ~/lane-wt/logs/.fill-started-recent 2>/dev/null; then   # v6.1: never start the same job twice
    echo "$(date) fill DEDUPE skip $j (already running/started <10m)" >> $L
    q_remove $j; continue
  fi
  lease_out=$(python3 "$LEASE" "$j" ~/lane-wt/logs/q-$j.prompt 2>&1)
  lease_rc=$?
  echo "$(date) fill lease $j rc=$lease_rc $lease_out" >> $L
  if (( lease_rc != 0 )); then
    # v3 (B5): defer, don't drop. The job stays queued and is retried after FILL_DEFER_S; fill-queue.py drops it
    # (and logs DROP) only after FILL_DEFER_MAX refusals in a row.
    echo "$(date) fill DEFER $j (lease rc=$lease_rc)" >> $L
    q_defer $j; sleep 5; continue
  fi

  LOG=~/lane-wt/logs/q-$j.log
  claimf=$(print -r -- "$lease_out" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read().strip().splitlines()[-1]).get("claim",""))' 2>/dev/null)   # lane-ops v2: last JSON line (log lines before it broke the parse -> claim never released)
  REL=""; [[ -n $claimf && $claimf == */coord/claims/* ]] && REL="; mv -f '$claimf' ~/Documents/bob-overnight-inject/coord/claims-released/ 2>/dev/null"   # v6.1: release claim when the lane exits
  # lane-ops v2: hold the claim as a heartbeat lease for the life of the screen; lane-lease.sh releases it on any exit
  # (incl. screen -X quit). The old mv-on-exit (REL) only ran on a clean exit, so killed lanes held claims for 5 h.
  LW=(); [[ -n $REL && -x ~/lane-wt/logs/lane-lease.sh ]] && { LW=(~/lane-wt/logs/lane-lease.sh $claimf - --); REL=""; }
  FIN="echo EXIT \$? \$(date) >> $LOG; ~/lane-wt/logs/lane-result.sh $LOG $j$REL"   # v6.4 recover RESULT
  case $prov in
    codex)
      eff=$CODEX_CHEAP_EFFORT; [[ $tier == high ]] && eff=$CODEX_HIGH_EFFORT; [[ $tier == xhigh ]] && eff=xhigh
      # v3 (item 10): NucBox-only. If the NucBox can't take it now, release the lease and defer; never run on the Mini
      # (even CODEX_HOST=mini is refused at launch).
      chost=$(codex_host_pick 2>/dev/null)
      if [[ -z $chost ]]; then
        echo "$(date) fill codex host unavailable for $j at launch -> DEFER (no Mini fallback)" >> $L
        [[ -n $claimf ]] && python3 ~/Documents/bob-overnight-inject/bin/claim-gate.py release --claim $claimf --owner lane-fill --status HELD >/dev/null 2>&1
        q_defer $j 300; sleep 5; continue
      fi
      if [[ $chost == nuc ]]; then
        ${=SSH} "mkdir -p ~/work/results ~/work/q-$j && cat > ~/work/results/q-$j.prompt" < ~/lane-wt/logs/q-$j.prompt
        LANE_REMOTE_NAME=q-$j LANE_REMOTE_SSH=$SSH screen -dmS lane-codex-nuc-$j $LW zsh -c "$SSH 'bash -l ~/nuc-tools/lane-supervise.sh run q-$j ${LANE_LEASE_S:-900} -- bash -l ~/nuc-tools/lane-run-codex.sh q-$j $eff' > $LOG 2>&1; $FIN"
        printf "%s\t%s\tcodex-nuc\t%s\tstart\n" "$(date +%F\ %T)" $j $eff >> $CODEX_LOG
        echo "$(date) fill codex host=nuc model=${CODEX_MODEL:-gpt-6-astra} effort=$eff job=$j" >> $L
      else
        echo "$(date) fill codex REFUSED host=mini (NucBox-only)" >> $L
        [[ -n $claimf && $claimf == */coord/claims/* ]] && mv -f "$claimf" ~/Documents/bob-overnight-inject/coord/claims-released/ 2>/dev/null
        sleep 120
        continue
      fi;;
    gemini)
      LANE_REMOTE_NAME=q-$j LANE_REMOTE_SSH=$SSH screen -dmS lane-gemini-$j $LW zsh -c "~/lane-wt/logs/gemini-lane.sh $j > $LOG 2>&1; $FIN";;
    claude)
      w=~/lane-wt/q-$j; mkdir -p $w
      screen -dmS lane-claude-$j $LW zsh -c "cd $w && /opt/homebrew/bin/claude -p --model sonnet --permission-mode acceptEdits --allowedTools 'Read,Edit,Write,Glob,Grep,Bash(git:*),Bash(gh:*),Bash(npm:*),Bash(npx:*),Bash(node:*),Bash(pytest:*),Bash(python3:*)' \"\$(cat ~/lane-wt/logs/q-$j.prompt)\" </dev/null > $LOG 2>&1; $FIN";;
    cursor)
      m=$CURSOR_MODEL   # v5.3: only composer-2.5 is usable on Cursor until 10/21
      ${=SSH} "mkdir -p ~/work/results && cat > ~/work/results/q-$j.prompt" < ~/lane-wt/logs/q-$j.prompt
      LANE_REMOTE_NAME=q-$j LANE_REMOTE_SSH=$SSH screen -dmS lane-$prov-$j $LW zsh -c "$SSH 'bash -l ~/nuc-tools/lane-supervise.sh run q-$j ${LANE_LEASE_S:-900} -- bash -l ~/nuc-tools/lane-run-q.sh q-$j $m' > $LOG 2>&1; $FIN";;
    minimax)
      screen -dmS lane-minimax-$j $LW zsh -c "~/Documents/bob-overnight-inject/bin/review-tip-minimax.sh ~/lane-wt/logs/q-$j.prompt ~/lane-wt/logs/q-$j.minimax.md > $LOG 2>&1; cat ~/lane-wt/logs/q-$j.minimax.md >> $LOG 2>/dev/null; echo 'RESULT minimax-critique' >> $LOG; $FIN";;
  esac
  printf "%s\t%s\t%s\t%s\n" "$(date +%F\ %T)" $j $prov $tier >> ~/lane-wt/logs/provider-usage.tsv
  echo "$(date +%s) $j" >> ~/lane-wt/logs/.fill-started-recent
  echo "$(date) fill started $j prov=$prov tier=$tier load5=$(l5) running[codex=$(running codex) cursor=$(running cursor) gemini=$(running gemini) claude=$(running claude) minimax=$(running minimax)]" >> $L

  q_remove $j

  [[ $prov == codex ]] && sleep 180 || { [[ $prov == gemini ]] && sleep 15 || sleep 45; }
done

# helpers for fill.sh v5 / v6.5
. ~/lane-wt/logs/lane-route.conf
CAPJ=~/Documents/bob-overnight-inject/sync/ai-capacity.json
CODEX_LOG=~/lane-wt/logs/codex-usage.tsv
job_get(){ local f=~/lane-wt/logs/q-$1.lane k=$2 d=$3; [[ -f $f ]] && { v=$(grep -E "^$k=" $f | tail -1 | cut -d= -f2); [[ -n $v ]] && { echo $v; return; }; }; echo $d; }
job_tier(){ job_get $1 tier cheap; }
job_provider(){ local p=$(job_get $1 provider ""); [[ -n $p ]] && { echo $p; return; }
  case $(job_tier $1) in high|xhigh) echo codex;; *) echo ${DEFAULT_CHEAP_PROVIDER:-cursor};; esac; }
running(){ local n=$(screen -ls 2>/dev/null | grep -c "\.lane-$1-"); [[ $1 == codex ]] && n=$((n+$(screen -ls 2>/dev/null | grep -c "\.lane-q-"))); echo $n; }
codex_pace_ok(){ # $1=tier ; cheap codex only while under weekly pace
  [[ $1 == high || $1 == xhigh ]] && return 0
  python3 - "$CAPJ" "$CODEX_TARGET_PCT" "${CODEX_MANUAL_RESET_TS:-0}" <<'PY'
import json,sys,time
try:
  r=[x for x in json.load(open(sys.argv[1]))["rows"] if x["provider"].startswith("Codex")][0]
  used=float(r["used_pct"] or 0); rst=float(r["reset_ts"]); m=float(sys.argv[3])
  if m and float(r.get("observed_ts") or 0) < m: used=0.0; rst=m+7*86400
  el=max(0,min(1,1-(rst-time.time())/(7*86400)))
  sys.exit(0 if used <= el*float(sys.argv[2])+5 else 1)
except Exception: sys.exit(1)
PY
}
mm_today(){ local n; n=$(grep -c "^$(date +%F).*minimax" ~/lane-wt/logs/provider-usage.tsv 2>/dev/null); echo ${n:-0}; }  # grok 10/16: old "|| echo 0" printed "0\n0" at zero -> arithmetic error -> minimax never picked
karen_busy(){ screen -ls 2>/dev/null | grep -qi karen; }
# v6.5: NucBox lane count includes cursor + gemini + claude + codex-on-nuc (shared 4–5 cap + load<12)
running_codex_nuc(){ screen -ls 2>/dev/null | grep -c "\.lane-codex-nuc-"; }
nuc_lane_count(){ echo $(( $(running cursor) + $(running gemini) + $(running claude) + $(running_codex_nuc) )); }  # Mini-hosted lane-codex-* excluded
nuc_ok(){ local n l; n=$(nuc_lane_count); l=$(${=SSH} 'cut -d" " -f1 /proc/loadavg|cut -d. -f1' 2>/dev/null) || return 1; [[ -n $l ]] || return 1; local cap=4; (( l < 10 )) && cap=5; (( l < 12 && n < cap )); }
nuc_codex_ok(){ # Codex on NucBox: shared slot/load cap; Windows CLI must be reachable
  nuc_ok || return 1
  ${=SSH} 'test -x ~/nuc-tools/codex-win.sh && test -x "$(ls -td /mnt/c/Users/rupret/AppData/Local/OpenAI/Codex/bin/*/codex.exe 2>/dev/null | head -1)"' 2>/dev/null
}
codex_cap_ok(){ local l=$(sysctl -n vm.loadavg | awk '{print int($3)}'); (( l > 10 )) && (( $(running codex) >= 2 )) && return 1; return 0; }  # v5.1: Codex 3, drop to 2 when 15-min load trends >10
codex_host_pick(){ # echo nuc|mini ; prefer NucBox when CODEX_HOST=auto/nuc and nuc_codex_ok
  case ${CODEX_HOST:-auto} in
    nuc) nuc_codex_ok && echo nuc || return 1;;
    mini) echo mini; return 0;;
    auto|*) nuc_codex_ok && echo nuc || echo mini; return 0;;
  esac
}
codex_start_ok(){ # $1=tier — host-aware gate for starting a Codex lane (does not raise TGT)
  (( $(running codex) < TGT_codex )) || return 1
  codex_pace_ok $1 || return 1
  local h; h=$(codex_host_pick) || return 1
  if [[ $h == nuc ]]; then return 0; fi
  mini_ok && codex_cap_ok
}
gemini_ok(){ [[ -f ~/lane-wt/logs/gemini.pause ]] && return 1; local h=$(awk -F'\t' -v c="$(date -v-1H '+%F %T')" '$1>=c{t+=$6} END{printf "%d", t}' ~/lane-wt/logs/gemini-spend.txt 2>/dev/null); (( ${h:-0} < ${GEMINI_HOURLY_PACE:-20} )) || return 1
  local nl; nl=$(${=SSH} 'cut -d" " -f1 /proc/loadavg|cut -d. -f1' 2>/dev/null) || return 1; [[ -n $nl ]] && (( nl < 11 )) || return 1   # v6.3: cap on NucBox load (clones/tests run there)
  local l s; l=$(sysctl -n vm.loadavg | awk '{print int($3)}'); s=$(sysctl -n vm.swapusage | awk '{gsub("M","",$3);gsub("M","",$6); printf "%d", $6*100/$3}')
  (( l < 10 && s < 80 )) || (( $(running gemini) < 4 )) || return 1; return 0; }  # Mini only makes HTTP calls now; over Mini guard hold at 4

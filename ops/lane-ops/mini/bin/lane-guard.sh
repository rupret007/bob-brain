# sourced helpers for Mini lanes. No secrets printed.
export PATH=/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH
mini_ok() { # 0 if Mini may run tests: 1-min load<=MINI_LOAD_MAX(10), swap<MINI_SWAP_MAX(80)%, free disk>=15G
  local l s d; l=$(sysctl -n vm.loadavg | awk '{print int($2)}')
  s=$(sysctl -n vm.swapusage | awk '{t=$3+0;u=$6+0; print (t>0)?int(u*100/t):0}')
  d=$(df -g / | awk 'NR==2{print $4}')
  MINI_STATE="load=$l swap=${s}% disk=${d}G"
  [ "$l" -le "${MINI_LOAD_MAX:-10}" ] && [ "$s" -lt "${MINI_SWAP_MAX:-80}" ] && [ "$d" -ge 15 ]; }
mini_wait() { local n=0; until mini_ok; do [ $n = 0 ] && echo "MINI-GUARD waiting ($MINI_STATE) $(date)"; n=$((n+1)); [ $n -gt ${MINI_WAIT_MAX:-120} ] && { echo "MINI-GUARD gave up ($MINI_STATE)"; return 1; }; sleep 30; done; }
gh_throttle() { # wait while GitHub core budget is low; min 1s spacing between calls
  local f=/tmp/.gh-throttle-last now rem reset; now=$(date +%s)
  [ -f $f ] && [ $((now-$(cat $f))) -lt 1 ] && sleep 1; date +%s > $f
  rem=$(gh api rate_limit -q '.resources.core.remaining' 2>/dev/null) || return 0
  if [ "${rem:-5000}" -lt "${GH_MIN_REMAINING:-300}" ]; then reset=$(gh api rate_limit -q '.resources.core.reset'); echo "GH-THROTTLE remaining=$rem sleeping until reset"; sleep $(( reset-now>0 ? reset-now+5 : 60 )); fi; }
lane_preflight() { # $1=SSH cmd string; prints problems, returns 1 on hard failure
  local bad=0; command -v gh >/dev/null || { echo "PREFLIGHT gh missing"; bad=1; }
  gh auth status >/dev/null 2>&1 || { echo "PREFLIGHT gh not authed"; bad=1; }
  [ -x $HOME/.local/bin/cursor-agent ] || echo "PREFLIGHT warn: mini cursor-agent missing (fallback unavailable)"
  [ "$(df -g / | awk 'NR==2{print $4}')" -ge 15 ] || { echo "PREFLIGHT Mini disk <15G"; bad=1; }
  return $bad; }

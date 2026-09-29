#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
BASE="$HOME/Documents/bob-overnight-inject"
WT="$BASE/workspaces/webbob-integrate-2057"
C="$BASE/conductor"
LOG="$C/logs/lane-integrate-deploy-2205.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date)"
echo "live before: $(curl -s http://127.0.0.1:8787/api/version)"
cd "$WT/webchat" || exit 1
# attempt 3 slot reused for ab50533 tip (prior attempt3 backed up as *-61ad058.json)
python3 deploy_integrate.py \
  --root "$BASE" \
  --candidate "$WT" \
  --draft-pr "https://github.com/rupret007/bob-brain/pull/17" \
  --expected-live "dff84e3" \
  --attempt 3 \
  --timeout 1800
EC=$?
echo "EXIT $EC $(date)"
echo "live after: $(curl -s http://127.0.0.1:8787/api/version)"
# Write deploy outcome marker
{
  echo "# INTEGRATE-DEPLOY-2205"
  echo "exit: $EC"
  echo "finished: $(date)"
  echo "live: $(curl -s http://127.0.0.1:8787/api/version)"
  echo "evidence: $C/reviews/WEBBOB-INTEGRATE-DEPLOYMENT-0927-attempt3.json"
  if [ "$EC" -eq 0 ]; then echo "RESULT: LIVE_PASS"; else echo "RESULT: FAIL_OR_ROLLBACK"; fi
} > "$C/reviews/INTEGRATE-DEPLOY-2205.md"
exit $EC

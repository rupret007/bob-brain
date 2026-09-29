#!/bin/bash
set -euo pipefail
export BOB_ROOT="/Users/jeffstory/Documents/bob-overnight-inject"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
set -a
[ -f "/Users/jeffstory/Documents/bob-overnight-inject/conductor/keys.env" ] && . "/Users/jeffstory/Documents/bob-overnight-inject/conductor/keys.env"
set +a
cd "/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat"
echo START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# verify tip + BOTH_PASS gate before calling deploy
TIP=$(git -C "/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057" rev-parse HEAD)
echo TIP=$TIP
if [ "$TIP" != "badc732c740625dd4a15b1774db09815c7a5ed99" ]; then
  echo "REFUSE deploy: tip mismatch"
  exit 2
fi
if ! grep -q 'GATE: BOTH_PASS tip=badc732' "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/INTEGRATE-LIVE-0204.md" 2>/dev/null; then
  echo "REFUSE deploy: INTEGRATE-LIVE-0204 not BOTH_PASS"
  exit 3
fi
python3 -u deploy_integrate.py \
  --root "/Users/jeffstory/Documents/bob-overnight-inject" \
  --candidate "/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057" \
  --draft-pr "https://github.com/rupret007/bob-brain/pull/17" \
  --expected-live "dff84e3" \
  --attempt 2 \
  --timeout 1800
ec=$?
echo EXIT=$ec
echo AFTER=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -sS http://127.0.0.1:8787/api/version || true
echo
exit $ec

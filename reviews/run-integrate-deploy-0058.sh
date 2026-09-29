#!/bin/bash
set -euo pipefail
export BOB_ROOT="/Users/jeffstory/Documents/bob-overnight-inject"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
set -a
[ -f "/Users/jeffstory/Documents/bob-overnight-inject/conductor/keys.env" ] && . "/Users/jeffstory/Documents/bob-overnight-inject/conductor/keys.env"
set +a
cd "/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/webchat"
echo START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 -u deploy_integrate.py   --root "/Users/jeffstory/Documents/bob-overnight-inject"   --candidate "/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057"   --draft-pr "https://github.com/rupret007/bob-brain/pull/17"   --expected-live "dff84e3"   --attempt 1   --timeout 1800
ec=$?
echo EXIT=$ec
echo AFTER=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -sS http://127.0.0.1:8787/api/version || true
echo
exit $ec

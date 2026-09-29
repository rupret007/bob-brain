#!/bin/bash
set -euo pipefail
export BOB_ROOT="/Users/jeffstory/Documents/bob-overnight-inject"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
set -a; [ -f "/Users/jeffstory/Documents/bob-overnight-inject/conductor/keys.env" ] && . "/Users/jeffstory/Documents/bob-overnight-inject/conductor/keys.env"; set +a
cd "/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057"
echo START=$(date -u +%Y-%m-%dT%H:%M:%SZ) | tee "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/codex-integrate-freeze-0058.log"
# Try common unattended forms
if codex exec --help >/dev/null 2>&1; then
  codex exec --full-auto < "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/PROMPT-integrate-session-freeze-0058.md" >> "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/codex-integrate-freeze-0058.log" 2>&1 ||   codex exec - < "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/PROMPT-integrate-session-freeze-0058.md" >> "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/codex-integrate-freeze-0058.log" 2>&1
else
  codex --full-auto < "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/PROMPT-integrate-session-freeze-0058.md" >> "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/codex-integrate-freeze-0058.log" 2>&1
fi
ec=$?
echo EXIT=$ec | tee -a "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/codex-integrate-freeze-0058.log"
echo AFTER=$(date -u +%Y-%m-%dT%H:%M:%SZ) | tee -a "/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/codex-integrate-freeze-0058.log"
exit $ec

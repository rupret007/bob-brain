#!/bin/bash
set -euo pipefail
export BOB_ROOT="/Users/jeffstory/Documents/bob-overnight-inject"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
set -a; [ -f "/Users/jeffstory/Documents/bob-overnight-inject/conductor/keys.env" ] && . "/Users/jeffstory/Documents/bob-overnight-inject/conductor/keys.env"; set +a
cd "/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/codex-integrate-apiworkers-0204.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/PROMPT-integrate-apiworkers-live-0204.md"
echo START=$(date -u +%Y-%m-%dT%H:%M:%SZ) | tee "$LOG"
if codex exec --help >/dev/null 2>&1; then
  codex exec --full-auto < "$PROMPT" >> "$LOG" 2>&1 || codex exec - < "$PROMPT" >> "$LOG" 2>&1
else
  codex --full-auto < "$PROMPT" >> "$LOG" 2>&1
fi
ec=$?
echo EXIT=$ec | tee -a "$LOG"
echo AFTER=$(date -u +%Y-%m-%dT%H:%M:%SZ) | tee -a "$LOG"
exit $ec

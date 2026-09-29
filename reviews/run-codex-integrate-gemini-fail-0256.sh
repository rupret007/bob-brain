#!/bin/bash
set -euo pipefail
export BOB_ROOT="/Users/jeffstory/Documents/bob-overnight-inject"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
set -a
[ -f "$BOB_ROOT/conductor/keys.env" ] && . "$BOB_ROOT/conductor/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
cd "$BOB_ROOT/workspaces/webbob-integrate-2057"
LOG="$BOB_ROOT/conductor/reviews/codex-integrate-gemini-fail-0256.log"
PROMPT="$BOB_ROOT/conductor/reviews/PROMPT-integrate-gemini-fail-0256.md"
mkdir -p "$BOB_ROOT/conductor/logs"
echo START=$(date -u +%Y-%m-%dT%H:%M:%SZ) tip=$(git rev-parse HEAD) | tee "$LOG"
if codex exec --help >/dev/null 2>&1; then
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" >>"$LOG" 2>&1 \
    || codex exec --full-auto "$(cat "$PROMPT")" >>"$LOG" 2>&1 \
    || codex exec --full-auto < "$PROMPT" >>"$LOG" 2>&1
else
  codex --full-auto < "$PROMPT" >>"$LOG" 2>&1
fi
ec=$?
echo EXIT=$ec | tee -a "$LOG"
echo AFTER=$(date -u +%Y-%m-%dT%H:%M:%SZ) | tee -a "$LOG"
exit $ec

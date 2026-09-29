#!/bin/bash
# QUEUED STUB — read-only investigation, no code changes, no deploy. Not auto-launched.
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
LOG="$C/logs/lane-webbob-ui-investigate-queued-0916.log"
PROMPT="$C/prompts/lane-webbob-ui-investigate-queued-0916.md"
{
  echo "START $(date) lane-webbob-ui-investigate-queued-0916 (QUEUED)"
  cd "$C" || exit 1
  echo "cwd=$(pwd) claude=$(which claude)"
  claude -p "$(cat "$PROMPT")" --permission-mode bypassPermissions
  echo "EXIT $? $(date)"
} >>"$LOG" 2>&1

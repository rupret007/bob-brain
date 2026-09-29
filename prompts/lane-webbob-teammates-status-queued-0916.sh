#!/bin/bash
# QUEUED STUB — investigation + one clarifying question only, no code changes. Not auto-launched.
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
LOG="$C/logs/lane-webbob-teammates-status-queued-0916.log"
PROMPT="$C/prompts/lane-webbob-teammates-status-queued-0916.md"
{
  echo "START $(date) lane-webbob-teammates-status-queued-0916 (QUEUED)"
  cd "$HOME/Documents/bob-overnight-inject" || exit 1
  echo "cwd=$(pwd) claude=$(which claude)"
  claude -p "$(cat "$PROMPT")" --permission-mode bypassPermissions
  echo "EXIT $? $(date)"
} >>"$LOG" 2>&1

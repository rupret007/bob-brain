#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-gaps-1725"
LOG="$C/logs/lane-webbob-gaps-fix-0004.log"
{
  echo "START $(date)"
  cd "$WT" || exit 1
  echo "cwd=$(pwd) head=$(git rev-parse --short HEAD) claude=$(which claude)"
  claude -p "$(cat "$C/prompts/lane-webbob-gaps-fix-0004.md")" --permission-mode bypassPermissions
  echo "EXIT $? $(date)"
} >>"$LOG" 2>&1

#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057"
LOG="$C/logs/lane-webbob-integrate-fix-2205.log"
{
  echo "START $(date)"
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) codex=$(which codex)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$C/prompts/lane-webbob-integrate-fix-2205.md")"
  echo "EXIT $? $(date)"
} >>"$LOG" 2>&1

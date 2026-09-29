#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/wt-webbob-media-0927"
LOG="$C/logs/lane-webbob-media-fix-2205.log"
{
  echo "START $(date)"
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) cursor=$(ls ~/.local/bin/cursor-agent)"
  ~/.local/bin/cursor-agent -p --force --trust "$(cat "$C/prompts/lane-webbob-media-fix-2205.md")"
  echo "EXIT $? $(date)"
} >>"$LOG" 2>&1

#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
REPO="$HOME/Documents/bob-overnight-inject/bob-brain"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-maxmode-1008"
LOG="$C/logs/lane-webbob-maxmode-reliability-1008.log"
PROMPT="$C/prompts/lane-webbob-maxmode-reliability-1008.md"
{
  echo "START $(date) lane-webbob-maxmode-reliability-1008"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  git -C "$REPO" fetch origin draft/webbob-clean-0927 draft/webbob-maxmode-0927 2>&1 || true
  if [ ! -d "$WT/.git" ]; then
    git -C "$REPO" worktree add -f "$WT" -b draft/webbob-maxmode-reliability-1008 origin/draft/webbob-clean-0927
  fi
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) claude=$(which claude)"
  claude -p "$(cat "$PROMPT")" --permission-mode bypassPermissions </dev/null
  echo "EXIT $? $(date)"
  ls -la "$C/reviews/MAXMODE-FIXED-1008.md" 2>/dev/null || echo "MAXMODE-FIXED-1008 pending"
} >>"$LOG" 2>&1

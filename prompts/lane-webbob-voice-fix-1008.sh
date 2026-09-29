#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
REPO="$HOME/Documents/bob-overnight-inject/bob-brain"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-voice-1008"
LOG="$C/logs/lane-webbob-voice-fix-1008.log"
PROMPT="$C/prompts/lane-webbob-voice-fix-1008.md"
{
  echo "START $(date) lane-webbob-voice-fix-1008"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  git -C "$REPO" fetch origin draft/webbob-voice-0927 draft/webbob-clean-0927 2>&1 || true
  if [ ! -d "$WT/.git" ]; then
    if git -C "$REPO" rev-parse --verify origin/draft/webbob-voice-0927 >/dev/null 2>&1; then
      git -C "$REPO" worktree add -f "$WT" -b draft/webbob-voice-fix-1008 origin/draft/webbob-voice-0927
    else
      git -C "$REPO" worktree add -f "$WT" -b draft/webbob-voice-fix-1008 origin/draft/webbob-clean-0927
    fi
  fi
  cd "$WT" || exit 1
  git checkout draft/webbob-voice-fix-1008 2>/dev/null || git checkout -B draft/webbob-voice-fix-1008 HEAD
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) full=$(git rev-parse HEAD) branch=$(git branch --show-current) codex=$(which codex)"
  echo "live: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
  ls -la "$C/reviews/VOICE-FIXED-1008.md" 2>/dev/null || echo "VOICE-FIXED-1008 pending"
} >>"$LOG" 2>&1

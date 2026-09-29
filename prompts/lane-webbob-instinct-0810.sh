#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
REPO="/Users/jeffstory/Documents/bob-overnight-inject/bob-brain"
WT="/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-instinct-0810"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-instinct-0810.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-instinct-0810.md"
{
  echo "START $(date) lane-webbob-instinct-0810"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  git -C "$REPO" fetch origin draft/webbob-clean-0927
  if [ ! -d "$WT/.git" ]; then
    git -C "$REPO" worktree add -f "$WT" -b draft/webbob-instinct-0810 origin/draft/webbob-clean-0927 || \
      git -C "$REPO" worktree add -f "$WT" origin/draft/webbob-clean-0927
  fi
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) full=$(git rev-parse HEAD) codex=$(which codex)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
  ls -la "$C/reviews/INSTINCT-FIXED-0810.md" "$C/reviews/INSTINCT-READY-0810.md" "$C/reviews/INSTINCT-BLOCKER-0810.md" 2>/dev/null || echo "instinct markers pending"
} >>"$LOG" 2>&1

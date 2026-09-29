#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
REPO="/Users/jeffstory/Documents/bob-overnight-inject/bob-brain"
WT="/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-texting-diagdump-fix-0916.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-texting-diagdump-fix-0916.md"
{
  echo "START $(date) lane-webbob-texting-diagdump-fix-0916"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  git -C "$REPO" fetch origin draft/webbob-texting-onto-a777736 draft/webbob-clean-0927 || true
  if [ ! -d "$WT/.git" ]; then
    echo "worktree missing; creating from origin/draft/webbob-texting-onto-a777736"
    git -C "$REPO" worktree add -f "$WT" -b draft/webbob-texting-diagdump-fix-0916 origin/draft/webbob-texting-onto-a777736 || \
      git -C "$REPO" worktree add -f "$WT" origin/draft/webbob-texting-onto-a777736
  fi
  cd "$WT" || exit 1
  # Prefer tip 9cfe548 / branch draft/webbob-texting-onto-a777736; cut successor if needed
  git fetch origin draft/webbob-texting-onto-a777736 2>/dev/null || true
  git checkout draft/webbob-texting-onto-a777736 2>/dev/null || true
  git reset --hard origin/draft/webbob-texting-onto-a777736 2>/dev/null || true
  if ! git rev-parse --verify draft/webbob-texting-diagdump-fix-0916 >/dev/null 2>&1; then
    git checkout -B draft/webbob-texting-diagdump-fix-0916 HEAD || true
  else
    git checkout draft/webbob-texting-diagdump-fix-0916 2>/dev/null || true
    git reset --hard origin/draft/webbob-texting-onto-a777736 2>/dev/null || true
  fi
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) full=$(git rev-parse HEAD) branch=$(git branch --show-current) codex=$(which codex)"
  echo "live before: $(curl -sS http://127.0.0.1:8787/api/version || true)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
  echo "live after: $(curl -sS http://127.0.0.1:8787/api/version || true)"
  ls -la "$C/reviews/TEXTING-DEPLOY-0916.md" "$C/reviews/TEXTING-FIXED-0916.md" 2>/dev/null || echo "markers pending"
} >>"$LOG" 2>&1

#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
REPO="/Users/jeffstory/Documents/bob-overnight-inject/bob-brain"
WT="/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-jobcomplete-1107"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-texting-jobcomplete-fix-1107.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-texting-jobcomplete-fix-1107.md"
{
  echo "START $(date) lane-webbob-texting-jobcomplete-fix-1107"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  git -C "$REPO" fetch origin draft/webbob-texting-diagdump-fix-0916 draft/webbob-clean-0927 || true
  if [ ! -d "$WT/.git" ]; then
    echo "worktree missing; creating from origin/draft/webbob-texting-diagdump-fix-0916 @ 1ca5e12"
    git -C "$REPO" worktree add -f "$WT" -b draft/webbob-texting-jobcomplete-fix-1107 origin/draft/webbob-texting-diagdump-fix-0916 ||       git -C "$REPO" worktree add -f "$WT" origin/draft/webbob-texting-diagdump-fix-0916
  fi
  cd "$WT" || exit 1
  git fetch origin draft/webbob-texting-diagdump-fix-0916 2>/dev/null || true
  if ! git rev-parse --verify draft/webbob-texting-jobcomplete-fix-1107 >/dev/null 2>&1; then
    git checkout -B draft/webbob-texting-jobcomplete-fix-1107 origin/draft/webbob-texting-diagdump-fix-0916 ||       git checkout -B draft/webbob-texting-jobcomplete-fix-1107 1ca5e12e06c9352ebf38005bcf8e764d03307c3b
  else
    git checkout draft/webbob-texting-jobcomplete-fix-1107 2>/dev/null || true
  fi
  # Ensure base is the failed tip unless branch already advanced
  CUR=$(git rev-parse HEAD)
  if [ "$CUR" = "1ca5e12e06c9352ebf38005bcf8e764d03307c3b" ] || git merge-base --is-ancestor 1ca5e12e06c9352ebf38005bcf8e764d03307c3b HEAD; then
    echo "base ok tip=$(git rev-parse --short HEAD)"
  else
    git reset --hard 1ca5e12e06c9352ebf38005bcf8e764d03307c3b || true
  fi
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) full=$(git rev-parse HEAD) branch=$(git branch --show-current) codex=$(which codex)"
  echo "live before: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
  echo "live after: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  ls -la "$C/reviews/TEXTING-DEPLOY-1107.md" "$C/reviews/TEXTING-FIXED-1107.md" 2>/dev/null || echo "markers pending"
} >>"$LOG" 2>&1

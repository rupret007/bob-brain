#!/bin/bash
# QUEUED STUB — dispatcher/scheduler code, independent of webchat feature deploy order. Not auto-launched.
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
REPO="$HOME/Documents/bob-overnight-inject/bob-brain"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-maxmode-reliability-0916"
LOG="$C/logs/lane-webbob-maxmode-reliability-queued-0916.log"
PROMPT="$C/prompts/lane-webbob-maxmode-reliability-queued-0916.md"
{
  echo "START $(date) lane-webbob-maxmode-reliability-queued-0916 (QUEUED)"
  git -C "$REPO" fetch origin draft/webbob-clean-0927 2>&1
  if [ ! -d "$WT/.git" ]; then
    git -C "$REPO" worktree add -f "$WT" -b draft/webbob-maxmode-reliability-0916 origin/draft/webbob-clean-0927
  fi
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) codex=$(which codex)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
} >>"$LOG" 2>&1

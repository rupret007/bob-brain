#!/bin/bash
# QUEUED STUB — do not run until texting is confirmed LIVE (see .md gate). Not auto-launched.
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
REPO="$HOME/Documents/bob-overnight-inject/bob-brain"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-gaps-1725"
LOG="$C/logs/lane-webbob-gaps-deploy-queued-0916.log"
PROMPT="$C/prompts/lane-webbob-gaps-deploy-queued-0916.md"
{
  echo "START $(date) lane-webbob-gaps-deploy-queued-0916 (QUEUED)"
  git -C "$REPO" fetch origin draft/webbob-gaps-1725 2>&1
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) codex=$(which codex)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
} >>"$LOG" 2>&1

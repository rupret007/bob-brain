#!/bin/bash
# QUEUED STUB — last in deploy order; do not run until texting/gaps/media/voice/UI are all LIVE. Not auto-launched.
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
REPO="$HOME/Documents/bob-overnight-inject/bob-brain"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-instinct-0810"
LOG="$C/logs/lane-webbob-instinct-deploy-queued-0916.log"
PROMPT="$C/prompts/lane-webbob-instinct-deploy-queued-0916.md"
{
  echo "START $(date) lane-webbob-instinct-deploy-queued-0916 (QUEUED)"
  git -C "$REPO" fetch origin draft/webbob-instinct-0810 2>&1
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) codex=$(which codex)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
} >>"$LOG" 2>&1

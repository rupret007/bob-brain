#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420"
LOG="$C/logs/lane-webbob-texting-onto-integrate-0420.log"
PROMPT="$C/prompts/lane-webbob-texting-onto-integrate-0420.md"
{
  echo "RESTART $(date)"
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) full=$(git rev-parse HEAD) codex=$(which codex)"
  # Pass prompt as argv; close stdin so codex does not wait for more input.
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
} >>"$LOG" 2>&1

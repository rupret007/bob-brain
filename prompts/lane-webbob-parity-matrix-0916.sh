#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-parity-matrix-0916.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-parity-matrix-0916.md"
{
  echo "START $(date) lane-webbob-parity-matrix-0916"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  cd "$C" || exit 1
  echo "cwd=$(pwd) claude=$(which claude)"
  claude -p "$(cat "$PROMPT")" --permission-mode bypassPermissions
  echo "EXIT $? $(date)"
  ls -la "$C/reviews/WEBBOB-PARITY-MATRIX.md" 2>/dev/null || echo "parity matrix pending"
} >>"$LOG" 2>&1

#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420"
LOG="$C/logs/lane-webbob-texting-deploy-0556.log"
PROMPT="$C/prompts/lane-webbob-texting-deploy-0556.md"
{
  echo "RESTART $(date)"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) full=$(git rev-parse HEAD) codex=$(which codex)"
  echo "live before: $(curl -sS http://127.0.0.1:8787/api/version || true)"
  # Pass prompt as argv; close stdin so codex does not wait for more input.
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
  echo "live after: $(curl -sS http://127.0.0.1:8787/api/version || true)"
  ls -la "$C/reviews/TEXTING-DEPLOY-0556.md" 2>/dev/null || echo "deploy marker missing"
} >>"$LOG" 2>&1

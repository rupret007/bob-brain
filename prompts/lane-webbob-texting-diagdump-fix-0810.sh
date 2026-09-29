#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
WT="/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-onto-a777736-0420"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-texting-diagdump-fix-0810.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-texting-diagdump-fix-0810.md"
{
  echo "START $(date) lane-webbob-texting-diagdump-fix-0810"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  if [ ! -d "$WT/.git" ]; then
    echo "worktree missing; creating from ce2482c"
    git -C /Users/jeffstory/Documents/bob-overnight-inject/bob-brain fetch origin draft/webbob-texting-onto-a777736 draft/webbob-clean-0927
    git -C /Users/jeffstory/Documents/bob-overnight-inject/bob-brain worktree add -f "$WT" -b draft/webbob-texting-diagdump-0810 ce2482cce311ce4317c1b3aca316f1ca446aeddb || \
      git -C /Users/jeffstory/Documents/bob-overnight-inject/bob-brain worktree add -f "$WT" ce2482cce311ce4317c1b3aca316f1ca446aeddb
  fi
  cd "$WT" || exit 1
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) full=$(git rev-parse HEAD) codex=$(which codex)"
  echo "live before: $(curl -sS http://127.0.0.1:8787/api/version || true)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
  echo "live after: $(curl -sS http://127.0.0.1:8787/api/version || true)"
  ls -la "$C/reviews/TEXTING-DEPLOY-0810.md" "$C/reviews/TEXTING-FIXED-0810.md" 2>/dev/null || echo "markers pending"
} >>"$LOG" 2>&1

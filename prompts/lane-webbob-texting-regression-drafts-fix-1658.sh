#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
REPO="/Users/jeffstory/Documents/bob-overnight-inject/bob-brain"
WT="/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-regression-drafts-1658"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-texting-regression-drafts-fix-1658.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-texting-regression-drafts-fix-1658.md"
BASE_TIP="c6b3e79218674703cd104d16c2a967ba0cb47221"
{
  echo "START $(date) lane-webbob-texting-regression-drafts-fix-1658"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  git -C "$REPO" fetch origin draft/webbob-texting-action-plan-fix-1605 draft/webbob-clean-0927 || true
  git -C "$REPO" cat-file -t "$BASE_TIP" || echo "WARN missing BASE_TIP"
  if [ ! -d "$WT/.git" ] && [ ! -f "$WT/.git" ]; then
    echo "worktree missing; creating from tip $BASE_TIP"
    git -C "$REPO" worktree add -f "$WT" -b draft/webbob-texting-regression-drafts-fix-1658 "$BASE_TIP" || \
      git -C "$REPO" worktree add -f "$WT" "$BASE_TIP"
  fi
  cd "$WT" || exit 1
  git fetch origin draft/webbob-clean-0927 draft/webbob-texting-action-plan-fix-1605 2>/dev/null || true
  if ! git rev-parse --verify draft/webbob-texting-regression-drafts-fix-1658 >/dev/null 2>&1; then
    git checkout -B draft/webbob-texting-regression-drafts-fix-1658 "$BASE_TIP"
  else
    git checkout draft/webbob-texting-regression-drafts-fix-1658 2>/dev/null || true
  fi
  CUR=$(git rev-parse HEAD)
  if [ "$CUR" = "$BASE_TIP" ] || git merge-base --is-ancestor "$BASE_TIP" HEAD; then
    echo "base ok tip=$(git rev-parse --short HEAD)"
  else
    git reset --hard "$BASE_TIP" || true
  fi
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) full=$(git rev-parse HEAD) branch=$(git branch --show-current) codex=$(which codex)"
  echo "live before: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  echo "screen_ls: $(screen -ls 2>&1 | tr '\n' ' ')"
  echo "attempt9_failure: live-replay Missing concrete regression test drafts (webchat-20bfc6f2) + still-failing 1035/dd47c4cb + f2c47c4c Action plan"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
  echo "live after: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  ls -la "$C/reviews/TEXTING-DEPLOY-1658.md" "$C/reviews/TEXTING-FIXED-1658.md" 2>/dev/null || echo "markers pending"
} >>"$LOG" 2>&1

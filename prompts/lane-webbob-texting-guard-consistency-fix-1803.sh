#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
REPO="/Users/jeffstory/Documents/bob-overnight-inject/bob-brain"
WT="/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-guard-consistency-1803"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-texting-guard-consistency-fix-1803.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-texting-guard-consistency-fix-1803.md"
BASE_TIP="d32d0f7244d191b85b429c3c8d0228ec0c9b4670"
BRANCH="draft/webbob-texting-guard-consistency-fix-1803"
{
  echo "START $(date) lane-webbob-texting-guard-consistency-fix-1803"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  git -C "$REPO" fetch origin draft/webbob-texting-regression-drafts-fix-1658 draft/webbob-clean-0927 || true
  git -C "$REPO" cat-file -t "$BASE_TIP" || echo "WARN missing BASE_TIP"
  if [ ! -d "$WT/.git" ] && [ ! -f "$WT/.git" ]; then
    echo "worktree missing; creating from tip $BASE_TIP"
    git -C "$REPO" worktree add -f "$WT" -b "$BRANCH" "$BASE_TIP" || \
      git -C "$REPO" worktree add -f "$WT" "$BASE_TIP"
  fi
  cd "$WT" || exit 1
  git fetch origin draft/webbob-clean-0927 draft/webbob-texting-regression-drafts-fix-1658 2>/dev/null || true
  if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    git checkout -B "$BRANCH" "$BASE_TIP"
  else
    git checkout "$BRANCH" 2>/dev/null || true
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
  echo "attempt10_failure: live-replay Regression draft contradicts literal guard outcome check_completion_json Missing or ambiguous required completion JSON (webchat-8e7eee34)"
  echo "launch_mode: codex exec without approval/sandbox bypass (Auto-review safer path)"
  if codex exec --help 2>&1 | grep -q -- '--full-auto'; then
    codex exec --full-auto "$(cat "$PROMPT")" </dev/null
  else
    codex exec "$(cat "$PROMPT")" </dev/null
  fi
  echo "EXIT $? $(date)"
  echo "live after: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  ls -la "$C/reviews/TEXTING-DEPLOY-1803.md" "$C/reviews/TEXTING-FIXED-1803.md" 2>/dev/null || echo "markers pending"
} >>"$LOG" 2>&1

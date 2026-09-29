#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
REPO="/Users/jeffstory/Documents/bob-overnight-inject/bob-brain"
WT="/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-disk-evidence-2003"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-texting-disk-evidence-fix-2003.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-texting-disk-evidence-fix-2003.md"
BASE_TIP="8260f800ae29dbcf306f3902227645d6da3cee97"
BRANCH="draft/webbob-texting-disk-evidence-fix-2003"
{
  echo "START $(date) lane-webbob-texting-disk-evidence-fix-2003"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  echo "disk: $(df -h /System/Volumes/Data | tail -1)"
  git -C "$REPO" fetch origin draft/webbob-texting-smoke-replay-fix-1901 draft/webbob-clean-0927 || true
  git -C "$REPO" cat-file -t "$BASE_TIP" || echo "WARN missing BASE_TIP"
  if [ ! -d "$WT/.git" ] && [ ! -f "$WT/.git" ]; then
    echo "worktree missing; creating from tip $BASE_TIP"
    git -C "$REPO" worktree add -f "$WT" -b "$BRANCH" "$BASE_TIP" || \
      git -C "$REPO" worktree add -f "$WT" "$BASE_TIP"
  fi
  cd "$WT" || exit 1
  git fetch origin draft/webbob-clean-0927 draft/webbob-texting-smoke-replay-fix-1901 2>/dev/null || true
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
  echo "attempt12_failure: ENOSPC during LIVE_REPLAY evidence checkpoint after smoke+19/19; rollback verified a777736"
  echo "launch_mode: codex exec without approval/sandbox bypass (Auto-review safer path)"
  if codex exec --help 2>&1 | grep -q -- '--full-auto'; then
    codex exec --full-auto "$(cat "$PROMPT")" </dev/null
  else
    codex exec "$(cat "$PROMPT")" </dev/null
  fi
  echo "EXIT $? $(date)"
  echo "live after: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  ls -la "$C/reviews/TEXTING-DEPLOY-2003.md" "$C/reviews/TEXTING-FIXED-2003.md" 2>/dev/null || echo "markers pending"
} >>"$LOG" 2>&1

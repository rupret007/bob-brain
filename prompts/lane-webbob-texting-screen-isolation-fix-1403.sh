#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
REPO="/Users/jeffstory/Documents/bob-overnight-inject/bob-brain"
WT="/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-screen-isolation-1403"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-texting-screen-isolation-fix-1403.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-texting-screen-isolation-fix-1403.md"
BASE_TIP="eb8029ed9fa17b26becb5487150b3d8981a5a0bb"
{
  echo "START $(date) lane-webbob-texting-screen-isolation-fix-1403"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  git -C "$REPO" fetch origin draft/webbob-texting-jobcomplete-fix-1207 draft/webbob-clean-0927 || true
  git -C "$REPO" cat-file -t e6c91a2efbf11d3c922469bcd912e675aea29c14 || echo "WARN missing e6c91a2 in bob-brain after fetch"
  if [ ! -d "$WT/.git" ]; then
    echo "worktree missing; creating from tip $BASE_TIP"
    git -C "$REPO" worktree add -f "$WT" -b draft/webbob-texting-screen-isolation-fix-1403 "$BASE_TIP" || \
      git -C "$REPO" worktree add -f "$WT" -b draft/webbob-texting-screen-isolation-fix-1403 origin/draft/webbob-texting-jobcomplete-fix-1207 || \
      git -C "$REPO" worktree add -f "$WT" "$BASE_TIP"
  fi
  cd "$WT" || exit 1
  git fetch origin draft/webbob-clean-0927 draft/webbob-texting-jobcomplete-fix-1207 2>/dev/null || true
  git fetch "$REPO" draft/webbob-clean-0927:refs/remotes/origin/draft/webbob-clean-0927 2>/dev/null || true
  if ! git rev-parse --verify draft/webbob-texting-screen-isolation-fix-1403 >/dev/null 2>&1; then
    git checkout -B draft/webbob-texting-screen-isolation-fix-1403 "$BASE_TIP" || \
      git checkout -B draft/webbob-texting-screen-isolation-fix-1403 origin/draft/webbob-texting-jobcomplete-fix-1207
  else
    git checkout draft/webbob-texting-screen-isolation-fix-1403 2>/dev/null || true
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
  echo "attempt6_failure: Unrelated screens changed during restart (svc-project-tick exited; durable svc-* unchanged)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
  echo "live after: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  ls -la "$C/reviews/TEXTING-DEPLOY-1403.md" "$C/reviews/TEXTING-FIXED-1403.md" 2>/dev/null || echo "markers pending"
} >>"$LOG" 2>&1

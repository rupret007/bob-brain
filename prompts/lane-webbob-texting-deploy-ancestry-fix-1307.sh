#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="/Users/jeffstory/Documents/bob-overnight-inject/conductor"
REPO="/Users/jeffstory/Documents/bob-overnight-inject/bob-brain"
WT="/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-deploy-ancestry-1307"
LOG="/Users/jeffstory/Documents/bob-overnight-inject/conductor/logs/lane-webbob-texting-deploy-ancestry-fix-1307.log"
PROMPT="/Users/jeffstory/Documents/bob-overnight-inject/conductor/prompts/lane-webbob-texting-deploy-ancestry-fix-1307.md"
BASE_TIP="eb8029ed9fa17b26becb5487150b3d8981a5a0bb"
{
  echo "START $(date) lane-webbob-texting-deploy-ancestry-fix-1307"
  set -a
  [ -f "$C/keys.env" ] && . "$C/keys.env"
  [ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
  set +a
  git -C "$REPO" fetch origin draft/webbob-texting-jobcomplete-fix-1207 draft/webbob-clean-0927 || true
  # Ensure clean merge object present in main repo
  git -C "$REPO" cat-file -t e6c91a2efbf11d3c922469bcd912e675aea29c14 || echo "WARN missing e6c91a2 in bob-brain after fetch"
  if [ ! -d "$WT/.git" ]; then
    echo "worktree missing; creating from tip $BASE_TIP"
    git -C "$REPO" worktree add -f "$WT" -b draft/webbob-texting-deploy-ancestry-fix-1307 "$BASE_TIP" || \
      git -C "$REPO" worktree add -f "$WT" -b draft/webbob-texting-deploy-ancestry-fix-1307 origin/draft/webbob-texting-jobcomplete-fix-1207 || \
      git -C "$REPO" worktree add -f "$WT" "$BASE_TIP"
  fi
  cd "$WT" || exit 1
  # Pull clean branch objects into this worktree so deploy ancestry cannot 128
  git fetch origin draft/webbob-clean-0927 draft/webbob-texting-jobcomplete-fix-1207 2>/dev/null || true
  git fetch "$REPO" draft/webbob-clean-0927:refs/remotes/origin/draft/webbob-clean-0927 2>/dev/null || true
  if ! git rev-parse --verify draft/webbob-texting-deploy-ancestry-fix-1307 >/dev/null 2>&1; then
    git checkout -B draft/webbob-texting-deploy-ancestry-fix-1307 "$BASE_TIP" || \
      git checkout -B draft/webbob-texting-deploy-ancestry-fix-1307 origin/draft/webbob-texting-jobcomplete-fix-1207
  else
    git checkout draft/webbob-texting-deploy-ancestry-fix-1307 2>/dev/null || true
  fi
  CUR=$(git rev-parse HEAD)
  if [ "$CUR" = "$BASE_TIP" ] || git merge-base --is-ancestor "$BASE_TIP" HEAD; then
    echo "base ok tip=$(git rev-parse --short HEAD)"
  else
    git reset --hard "$BASE_TIP" || true
  fi
  echo "cwd=$(pwd) tip=$(git rev-parse --short HEAD) full=$(git rev-parse HEAD) branch=$(git branch --show-current) codex=$(which codex)"
  echo "live before: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  echo "ancestry_probe_ws: $(git merge-base --is-ancestor eb8029ed9fa17b26becb5487150b3d8981a5a0bb e6c91a2efbf11d3c922469bcd912e675aea29c14; echo exit=$?)"
  echo "ancestry_probe_repo: $(git -C "$REPO" merge-base --is-ancestor eb8029ed9fa17b26becb5487150b3d8981a5a0bb e6c91a2efbf11d3c922469bcd912e675aea29c14; echo exit=$?)"
  codex exec --dangerously-bypass-approvals-and-sandbox "$(cat "$PROMPT")" </dev/null
  echo "EXIT $? $(date)"
  echo "live after: $(curl -sS --max-time 5 http://127.0.0.1:8787/api/version || true)"
  ls -la "$C/reviews/TEXTING-DEPLOY-1307.md" "$C/reviews/TEXTING-FIXED-1307.md" 2>/dev/null || echo "markers pending"
} >>"$LOG" 2>&1

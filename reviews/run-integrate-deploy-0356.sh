#!/bin/bash
set -euo pipefail
export BOB_ROOT="/Users/jeffstory/Documents/bob-overnight-inject"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
set -a
[ -f "$BOB_ROOT/conductor/keys.env" ] && . "$BOB_ROOT/conductor/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
C="$BOB_ROOT/conductor"
WT="$BOB_ROOT/workspaces/webbob-integrate-2057"
LOG="$C/reviews/INTEGRATE-DEPLOY-0356.log"
: >"$LOG"
exec > >(tee -a "$LOG") 2>&1
PR_URL="https://github.com/rupret007/bob-brain/pull/17"
echo START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "PR=$PR_URL (MERGED draft accepted by external deploy_integrate_0356.py — head matches a777736)"
echo "live before: $(curl -sS http://127.0.0.1:8787/api/version)"
TIP=$(git -C "$WT" rev-parse HEAD)
echo TIP=$TIP
if [ "$TIP" != "a777736b3f0a37c82b0c4c62be8c91117c4c9881" ]; then
  echo "REFUSE deploy: tip mismatch"; exit 2
fi
if ! grep -q 'GATE: BOTH_PASS tip=a777736' "$C/reviews/INTEGRATE-LIVE-0356.md"; then
  echo "REFUSE deploy: INTEGRATE-LIVE-0356 not BOTH_PASS"; exit 3
fi
LIVE_SHORT=$(curl -sS http://127.0.0.1:8787/api/version | python3 -c 'import sys,json; print(json.load(sys.stdin).get("short_sha",""))')
if [ "$LIVE_SHORT" != "dff84e3" ]; then
  echo "REFUSE deploy: expected live dff84e3 got $LIVE_SHORT"; exit 4
fi
gh pr view "$PR_URL" --json isDraft,state,headRefOid,baseRefName
# run EXTERNAL copy so candidate worktree stays clean (no local patch)
cd "$WT/webchat"
PYTHONPATH="$WT/webchat" python3 -u "$C/reviews/deploy_integrate_0356.py" \
  --root "$BOB_ROOT" \
  --candidate "$WT" \
  --draft-pr "$PR_URL" \
  --expected-live "dff84e3" \
  --attempt 3 \
  --timeout 1800
ec=$?
echo EXIT=$ec
echo AFTER=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LIVE=$(curl -sS http://127.0.0.1:8787/api/version || true)
echo "live after: $LIVE"
{
  echo "# INTEGRATE-DEPLOY-0356"
  echo "exit: $ec"
  echo "finished: $(date)"
  echo "tip: a777736"
  echo "draft_pr: $PR_URL"
  echo "deploy_runner: conductor/reviews/deploy_integrate_0356.py (MERGED draft accepted when head matches)"
  echo "attempt_slot: 3"
  echo "clean_note: merge c2d65cd reverted to 573ffab so history allows future PRs; tip still ancestor"
  echo "live: $LIVE"
  echo "evidence: $C/reviews/WEBBOB-INTEGRATE-DEPLOYMENT-0927-attempt3.json"
  if [ "$ec" -eq 0 ]; then echo "RESULT: LIVE_PASS"; else echo "RESULT: FAIL_OR_ROLLBACK"; fi
} > "$C/reviews/INTEGRATE-DEPLOY-0356.md"
exit $ec

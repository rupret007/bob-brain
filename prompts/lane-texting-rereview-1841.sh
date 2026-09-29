#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/wt-webbob-texting-0927"
LOG="$C/logs/lane-texting-rereview-1841.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date)"
BASE_SHA=$(git -C "$WT" rev-parse --short HEAD)
echo "watching texting tip from $BASE_SHA"
# Wait up to ~90 min for tip change OR TEXTING-FIXED-1841
deadline=$(( $(date +%s) + 5400 ))
while [ $(date +%s) -lt $deadline ]; do
  NOW=$(git -C "$WT" rev-parse --short HEAD)
  if [ -f "$C/reviews/TEXTING-FIXED-1841.md" ] || [ -f "$WT/reviews/TEXTING-FIXED-1841.md" ] || [ "$NOW" != "$BASE_SHA" ]; then
    echo "trigger tip=$NOW fixed_marker=$(ls $C/reviews/TEXTING-FIXED-1841.md $WT/reviews/TEXTING-FIXED-1841.md 2>/dev/null || true)"
    break
  fi
  sleep 45
done
NOW=$(git -C "$WT" rev-parse --short HEAD)
if [ "$NOW" = "$BASE_SHA" ] && [ ! -f "$C/reviews/TEXTING-FIXED-1841.md" ] && [ ! -f "$WT/reviews/TEXTING-FIXED-1841.md" ]; then
  echo "TIMEOUT no texting tip change; skip re-review $(date)"
  echo "EXIT 0 $(date)"
  exit 0
fi
# Fresh tip reviews via compat helpers (Gemini + MiniMax)
PROMPT_FILE=$(mktemp)
cat > "$PROMPT_FILE" <<'P'
Strict code review of draft/webbob-texting-0927 tip for Web Bob texting (draft→separate yes→send blocked/mock). List bugs/security/missing tests. End with VERDICT: PASS or VERDICT: FAIL and why. Focus: public() exclusions, hmac.compare_digest, E2E proof/evidence consistency, duplicate save, success message tests, no real send without owner yes.
P
OUT_G="$C/reviews/LIVE-GEMINI-draft_webbob-texting-0927-${NOW}-rereview.md"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-texting-0927-${NOW}-rereview.md"
echo "Running Gemini tip review -> $OUT_G"
# Use review-tip if available against worktree; else ask-gemini with diff context
if [ -x "$C/compat/ask-gemini.sh" ]; then
  # Provide tip context
  {
    echo "Branch tip SHA: $NOW"
    echo "Worktree: $WT"
    git -C "$WT" log --oneline -5
    echo '--- DIFFSTAT vs dff84e3 ---'
    git -C "$WT" diff --stat dff84e3...HEAD 2>/dev/null || git -C "$WT" diff --stat HEAD~5..HEAD
    echo '--- PROMPT ---'
    cat "$PROMPT_FILE"
  } > "$C/prompts/texting-rereview-ctx-${NOW}.md"
  "$C/compat/ask-gemini.sh" -f "$C/prompts/texting-rereview-ctx-${NOW}.md" --out "$OUT_G" || \
    python3 "$C/services/compat.py" gemini -f "$C/prompts/texting-rereview-ctx-${NOW}.md" --out "$OUT_G" || true
fi
if [ -x "$C/compat/ask-minimax.sh" ]; then
  "$C/compat/ask-minimax.sh" -f "$C/prompts/texting-rereview-ctx-${NOW}.md" --out "$OUT_M" || \
    python3 "$C/services/compat.py" minimax -f "$C/prompts/texting-rereview-ctx-${NOW}.md" --out "$OUT_M" || true
fi
# Summarize gate
{
  echo "# Texting re-review after fix — $(date)"
  echo "tip: $NOW"
  echo "gemini_out: $OUT_G"
  echo "minimax_out: $OUT_M"
  echo
  echo '## Gemini verdict lines'
  grep -E 'VERDICT|PASS|FAIL' "$OUT_G" 2>/dev/null | tail -10 || echo '(missing)'
  echo
  echo '## MiniMax verdict lines'
  grep -E 'VERDICT|PASS|FAIL' "$OUT_M" 2>/dev/null | tail -10 || echo '(missing)'
} > "$C/reviews/TEXTING-REREVIEW-1841.md"
rm -f "$PROMPT_FILE"
echo "DONE $(date)"
echo "EXIT 0 $(date)"

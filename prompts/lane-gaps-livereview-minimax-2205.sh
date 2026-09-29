#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-gaps-1725"
LOG="$C/logs/lane-gaps-livereview-minimax-2205.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date)"
NOW=$(git -C "$WT" rev-parse --short HEAD)
FULL=$(git -C "$WT" rev-parse HEAD)
echo "tip $NOW $FULL"
CTX="$C/prompts/gaps-livereview-ctx-${NOW}-2205.md"
{
  echo "# Strict LIVE MiniMax tip review draft/webbob-gaps-1725 @$NOW ($FULL)"
  echo
  echo "SCOPE: bob_gaps / profile memory / screenshot-window gaps ONLY."
  echo "Prior LIVE-GEMINI @ 70d59e3 = PASS. Offline GAPS-FIXED-2143 READY (atomic append_profile_memory via flock)."
  echo "Old MiniMax was on 3a7a571 — this is a fresh tip review of 70d59e3."
  echo "Do NOT fail for missing voice/media/texting. Cite only real symbols."
  echo "List CRITICAL/HIGH real bugs only. End with exactly: VERDICT: PASS or VERDICT: FAIL"
  echo
  echo '## FIXED-2143 summary'
  head -80 "$C/reviews/GAPS-FIXED-2143.md"
  echo
  echo '## git log'
  git -C "$WT" log --oneline 3a7a571..HEAD 2>/dev/null | head -30 || git -C "$WT" log --oneline -15
  echo '## diffstat vs live dff84e3 (gaps-focused)'
  git -C "$WT" diff --stat dff84e3...HEAD -- webchat/bob_gaps.py webchat/test_bob_gaps.py webchat/app.py 2>/dev/null | head -40
  echo '## bob_gaps.py flock / append_profile_memory'
  grep -n 'append_profile_memory\|fcntl\|flock\|profile.lock\|_trim_profile' "$WT/webchat/bob_gaps.py" 2>/dev/null | head -40
  echo '## relevant source excerpt'
  # extract function bodies roughly
  awk '/def append_profile_memory/,/^def /{print} /^def / && !/append_profile_memory/{if(seen++) exit}' "$WT/webchat/bob_gaps.py" 2>/dev/null | head -120
  sed -n '1,200p' "$WT/webchat/bob_gaps.py" 2>/dev/null | head -200
  echo '## tests'
  grep -n 'def test_' "$WT/webchat/test_bob_gaps.py" 2>/dev/null | head -40 || true
} > "$CTX"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-gaps-1725-${NOW}.md"
echo "MiniMax -> $OUT_M"
"$C/compat/ask-minimax.sh" -f "$CTX" --out "$OUT_M" || python3 "$C/services/compat.py" minimax --tip -f "$CTX" --out "$OUT_M" || true
if ! grep -q 'VERDICT' "$OUT_M" 2>/dev/null; then
  SHORT="$C/prompts/gaps-livereview-short-${NOW}-2205.md"
  {
    echo "Strict GAPS-ONLY review of tip $FULL. Focus atomic append_profile_memory + flock. End VERDICT: PASS or VERDICT: FAIL"
    head -40 "$C/reviews/GAPS-FIXED-2143.md"
    grep -n 'flock\|append_profile_memory' "$WT/webchat/bob_gaps.py" | head -30
  } > "$SHORT"
  "$C/compat/ask-minimax.sh" -f "$SHORT" --out "$OUT_M" || true
fi
echo "DONE $(date) verdict:"
grep -E 'VERDICT' "$OUT_M" 2>/dev/null | tail -5 || echo '(missing)'

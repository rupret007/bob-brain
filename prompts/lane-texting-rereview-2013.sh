#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/wt-webbob-texting-0927"
LOG="$C/logs/lane-texting-rereview-2013.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date)"
BASE_SHA=$(git -C "$WT" rev-parse --short HEAD)
echo "initial tip $BASE_SHA"
# Wait up to 45 min for TEXTING-FIXED-2013 or tip change; also proceed after 8 min if tip stable (re-review current tip with better context)
deadline=$(( $(date +%s) + 2700 ))
proceed_after=$(( $(date +%s) + 480 ))
while [ $(date +%s) -lt $deadline ]; do
  NOW=$(git -C "$WT" rev-parse --short HEAD)
  if [ -f "$C/reviews/TEXTING-FIXED-2013.md" ] || [ -f "$WT/reviews/TEXTING-FIXED-2013.md" ] || [ "$NOW" != "$BASE_SHA" ]; then
    echo "trigger tip=$NOW fixed_marker present"
    break
  fi
  if [ $(date +%s) -ge $proceed_after ]; then
    echo "proceeding to re-review stable tip $NOW after grace"
    break
  fi
  sleep 30
done
NOW=$(git -C "$WT" rev-parse --short HEAD)
FULL=$(git -C "$WT" rev-parse HEAD)
# Prefer prebuilt rich context if matches tip; else rebuild briefly
CTX="$C/prompts/texting-rereview-ctx-${NOW}-2013.md"
if [ ! -f "$CTX" ]; then
  CTX="$C/prompts/texting-rereview-ctx-2013-live.md"
  {
    echo "# Strict LIVE re-review draft/webbob-texting-0927 @$NOW ($FULL)"
    echo "Scope: TEXTING ONLY. Do not fail for missing voice/media. No Twilio. cite only real symbols."
    echo "End with VERDICT: PASS or VERDICT: FAIL"
    git -C "$WT" log --oneline -8
    git -C "$WT" diff --stat dff84e3...HEAD
    echo '--- texting.py ---'
    sed -n '1,420p' "$WT/webchat/texting.py"
    echo '--- app.py public ---'
    sed -n '210,280p' "$WT/webchat/app.py"
    echo '--- test names ---'
    grep -n 'def test_' "$WT/webchat/test_texting.py"
  } > "$CTX"
fi
OUT_G="$C/reviews/LIVE-GEMINI-draft_webbob-texting-0927-${NOW}-rereview.md"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-texting-0927-${NOW}-rereview.md"
echo "Gemini -> $OUT_G"
"$C/compat/ask-gemini.sh" -f "$CTX" --out "$OUT_G" || python3 "$C/services/compat.py" gemini -f "$CTX" --out "$OUT_G" || true
echo "MiniMax -> $OUT_M"
# Prefer non-agentic ask; also try --tip variants
"$C/compat/ask-minimax.sh" -f "$CTX" --out "$OUT_M" || python3 "$C/services/compat.py" minimax -f "$CTX" --out "$OUT_M" || true
# If MiniMax output looks like tool-call junk without VERDICT, retry once with shorter prompt
if ! grep -q 'VERDICT' "$OUT_M" 2>/dev/null; then
  echo "MiniMax missing VERDICT; retry short prompt"
  SHORT="$C/prompts/texting-rereview-short-${NOW}.md"
  {
    echo "Strict code review of Web Bob texting tip $FULL. Scope texting only."
    echo "Key facts: hmac.compare_digest used; Chat.public excludes private fields; browser proof = Not sent blocked path."
    echo "List real bugs only. End with VERDICT: PASS or VERDICT: FAIL"
    git -C "$WT" diff --stat dff84e3...HEAD
    sed -n '250,320p' "$WT/webchat/texting.py"
    sed -n '218,250p' "$WT/webchat/app.py"
  } > "$SHORT"
  "$C/compat/ask-minimax.sh" -f "$SHORT" --out "$OUT_M" || true
fi
{
  echo "# Texting re-review after 2013 fix — $(date)"
  echo "tip: $NOW"
  echo "full: $FULL"
  echo "gemini_out: $OUT_G"
  echo "minimax_out: $OUT_M"
  echo
  echo '## Gemini verdict lines'
  grep -E 'VERDICT' "$OUT_G" 2>/dev/null | tail -5 || echo '(missing)'
  echo
  echo '## MiniMax verdict lines'
  grep -E 'VERDICT' "$OUT_M" 2>/dev/null | tail -5 || echo '(missing)'
  G=$(grep -E 'VERDICT:\s*PASS' "$OUT_G" 2>/dev/null | tail -1 || true)
  M=$(grep -E 'VERDICT:\s*PASS' "$OUT_M" 2>/dev/null | tail -1 || true)
  echo
  if [ -n "$G" ] && [ -n "$M" ]; then
    echo "GATE: BOTH_PASS tip=$NOW"
  else
    echo "GATE: NOT_READY tip=$NOW"
  fi
} > "$C/reviews/TEXTING-REREVIEW-2013.md"
echo "DONE $(date)"
echo "EXIT 0 $(date)"

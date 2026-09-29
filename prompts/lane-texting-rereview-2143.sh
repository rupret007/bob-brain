#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/wt-webbob-texting-0927"
LOG="$C/logs/lane-texting-rereview-2143.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date)"
NOW=$(git -C "$WT" rev-parse --short HEAD)
FULL=$(git -C "$WT" rev-parse HEAD)
echo "tip $NOW $FULL"
CTX="$C/prompts/texting-rereview-ctx-${NOW}-2143.md"
{
  echo "# Strict LIVE re-review draft/webbob-texting-0927 @$NOW ($FULL)"
  echo
  echo "SCOPE: TEXTING ONLY (webchat/texting.py, texting_*.py, test_texting*.py, app.py texting hooks, static texting card)."
  echo "Do NOT fail for missing voice/media/iPhone. Do NOT fail for baseline services/draft_publish.py or dispatch_worker.py unless this tip changed them."
  echo "No Twilio. Cite only real symbols that exist in the provided sources."
  echo "Prior MiniMax FAILs on request_id equality / bare-yes / IndentationError were triaged as false or intentional; see TEXTING-FIXED-2014.md dispositions."
  echo "Focus on NEW tip changes since 78fa870 (lost Andrea reply → delivery_unconfirmed)."
  echo "End with exactly: VERDICT: PASS or VERDICT: FAIL"
  echo
  echo '## git log'
  git -C "$WT" log --oneline 78fa870..HEAD
  echo '## diffstat vs live dff84e3'
  git -C "$WT" diff --stat dff84e3...HEAD -- webchat/
  echo '## diff 78fa870..HEAD webchat (texting-focused)'
  git -C "$WT" diff 78fa870..HEAD -- webchat/texting.py webchat/texting_fixture.py webchat/test_texting.py webchat/test_texting_e2e.py webchat/texting_proof.py 2>/dev/null | head -400
  echo '--- texting.py confirm/handle ---'
  sed -n '250,360p' "$WT/webchat/texting.py"
  echo '--- test names ---'
  grep -n 'def test_' "$WT/webchat/test_texting.py" | head -80
  echo '--- FIXED-2014 summary ---'
  head -80 "$C/reviews/TEXTING-FIXED-2014.md"
} > "$CTX"
OUT_G="$C/reviews/LIVE-GEMINI-draft_webbob-texting-0927-${NOW}-rereview.md"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-texting-0927-${NOW}-rereview.md"
echo "Gemini -> $OUT_G"
"$C/compat/ask-gemini.sh" -f "$CTX" --out "$OUT_G" || python3 "$C/services/compat.py" gemini -f "$CTX" --out "$OUT_G" || true
echo "MiniMax -> $OUT_M"
"$C/compat/ask-minimax.sh" -f "$CTX" --out "$OUT_M" || python3 "$C/services/compat.py" minimax -f "$CTX" --out "$OUT_M" || true
if ! grep -q 'VERDICT' "$OUT_M" 2>/dev/null; then
  SHORT="$C/prompts/texting-rereview-short-${NOW}-2143.md"
  {
    echo "Strict TEXTING-ONLY code review of tip $FULL. Scope texting only; ignore voice/media gaps and baseline draft_publish."
    echo "Intentional: same request_id cannot confirm. Bare yes/ok never sends without token."
    echo "New: lost Andrea reply must stay delivery_unconfirmed not Not sent."
    echo "List real bugs only. End with VERDICT: PASS or VERDICT: FAIL"
    git -C "$WT" diff --stat 78fa870..HEAD -- webchat/
    sed -n '250,340p' "$WT/webchat/texting.py"
  } > "$SHORT"
  "$C/compat/ask-minimax.sh" -f "$SHORT" --out "$OUT_M" || true
fi
{
  echo "# Texting re-review 2143 — $(date)"
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
} > "$C/reviews/TEXTING-REREVIEW-2143.md"
echo "DONE $(date)"

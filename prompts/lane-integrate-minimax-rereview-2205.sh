#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
LOG="$C/logs/lane-integrate-minimax-rereview-2205.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date)"
CTX="$C/prompts/integrate-minimax-rereview-ctx-ab50533-2205.md"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-integrate-2057-ab50533-rereview.md"
OUT_G="$C/reviews/LIVE-GEMINI-draft_webbob-integrate-2057-ab50533.md"
echo "MiniMax rereview -> $OUT_M"
"$C/compat/ask-minimax.sh" -f "$CTX" --out "$OUT_M" || python3 "$C/services/compat.py" minimax --tip -f "$CTX" --out "$OUT_M" || true
# Also overwrite canonical LIVE-MINIMAX tip file with rereview if PASS/FAIL present
if grep -q 'VERDICT' "$OUT_M" 2>/dev/null; then
  cp "$OUT_M" "$C/reviews/LIVE-MINIMAX-draft_webbob-integrate-2057-ab50533.md"
fi
{
  echo "# INTEGRATE LIVE gate 2205 — $(date)"
  echo "tip: ab50533"
  echo "full: ab5053331d128372607194a0756b893d3872c7a0"
  echo "gemini_out: $OUT_G"
  echo "minimax_out: $OUT_M"
  echo "note: MiniMax rereview with FULL status_observation.py after FP triage"
  echo
  echo '## Gemini verdict lines'
  grep -E 'VERDICT' "$OUT_G" 2>/dev/null | tail -5 || echo '(missing)'
  echo
  echo '## MiniMax verdict lines (rereview)'
  grep -E 'VERDICT' "$OUT_M" 2>/dev/null | tail -5 || echo '(missing)'
  G=$(grep -E 'VERDICT:\s*PASS' "$OUT_G" 2>/dev/null | tail -1 || true)
  M=$(grep -E 'VERDICT:\s*PASS' "$OUT_M" 2>/dev/null | tail -1 || true)
  echo
  if [ -n "$G" ] && [ -n "$M" ]; then
    echo "GATE: BOTH_PASS tip=ab50533"
  else
    echo "GATE: FAIL tip=ab50533"
  fi
} > "$C/reviews/INTEGRATE-LIVE-2205.md"
# disposition note
{
  echo "# INTEGRATE MiniMax FP triage 2205"
  echo
  echo "Prior LIVE-MINIMAX @ ab50533 FAIL claimed undefined payload/snap and missing redact_snapshot."
  echo "Executor checked COMPLETE status_observation.py: all three symbols are defined."
  echo "Launched scoped MiniMax rereview with full file. Result below."
  echo
  cat "$C/reviews/INTEGRATE-LIVE-2205.md"
} > "$C/reviews/INTEGRATE-MINIMAX-FP-TRIAGE-2205.md"
echo "DONE $(date)"
cat "$C/reviews/INTEGRATE-LIVE-2205.md"

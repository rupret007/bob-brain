#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057"
LOG="$C/logs/lane-integrate-livereview-2205.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date)"
NOW=$(git -C "$WT" rev-parse --short HEAD)
FULL=$(git -C "$WT" rev-parse HEAD)
echo "tip $NOW $FULL"
if [ "$FULL" != "ab5053331d128372607194a0756b893d3872c7a0" ]; then
  echo "WARN tip mismatch expected ab50533 got $FULL — reviewing actual tip"
fi
CTX="$C/prompts/integrate-livereview-ctx-${NOW}-2205.md"
{
  echo "# Strict LIVE tip review draft/webbob-integrate-2057 @$NOW ($FULL)"
  echo
  echo "SCOPE: apiworkers / lane awareness / status_observation integrate ONLY."
  echo "Focus: status reply observations (digest, atomic write, history bind), worker/journal sample, integration gate evidence."
  echo "Do NOT fail for missing voice/media/texting/iPhone. Ignore out-of-lane gaps."
  echo "Prior live attempts on older tips failed 3× (WEBBOB-INTEGRATE-FAIL-0927.md); this tip ab50533 claims offline READY (319 webchat + 129 services + 56 evals)."
  echo "Cite only real symbols in provided sources. List CRITICAL/HIGH real bugs only."
  echo "End with exactly: VERDICT: PASS or VERDICT: FAIL"
  echo
  echo '## FIXED-2143 summary'
  head -90 "$C/reviews/INTEGRATE-FIXED-2143.md"
  echo
  echo '## git log vs live dff84e3'
  git -C "$WT" log --oneline dff84e3..HEAD | head -40
  echo '## diffstat vs live dff84e3'
  git -C "$WT" diff --stat dff84e3...HEAD -- webchat/ conductor/services/ 2>/dev/null | head -80
  echo '## key files (status observation / workers)'
  for f in webchat/app.py webchat/task_dispatch.py webchat/providers.py; do
    [ -f "$WT/$f" ] || continue
    echo "--- $f (grep status_observation / observation) ---"
    grep -n 'status_observation\|observation_digest\|StatusObservation\|worker.*journal\|lane.snapshot' "$WT/$f" 2>/dev/null | head -40 || true
  done
  echo '## recent status_observation-related hunks (bounded)'
  git -C "$WT" diff dff84e3...HEAD -- webchat/ | grep -E '^\+\+\+|^@@|status_observation|observation_|digest|atomic' | head -120
  echo '## test names mentioning observation/status'
  grep -n 'def test_.*\(status\|observ\|worker\|lane\|integrat\)' "$WT/webchat/test_webchat.py" 2>/dev/null | head -60 || true
  ls "$WT/webchat/evidence/" 2>/dev/null | head -20
} > "$CTX"
OUT_G="$C/reviews/LIVE-GEMINI-draft_webbob-integrate-2057-${NOW}.md"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-integrate-2057-${NOW}.md"
echo "Gemini -> $OUT_G"
"$C/compat/ask-gemini.sh" -f "$CTX" --out "$OUT_G" || python3 "$C/services/compat.py" gemini --tip -f "$CTX" --out "$OUT_G" || true
echo "MiniMax -> $OUT_M"
"$C/compat/ask-minimax.sh" -f "$CTX" --out "$OUT_M" || python3 "$C/services/compat.py" minimax --tip -f "$CTX" --out "$OUT_M" || true
# retry MiniMax shorter if no verdict
if ! grep -q 'VERDICT' "$OUT_M" 2>/dev/null; then
  SHORT="$C/prompts/integrate-livereview-short-${NOW}-2205.md"
  {
    echo "Strict INTEGRATE-ONLY code review of tip $FULL (status_observation + lane awareness)."
    echo "Offline claim: 319 webchat + 129 services + 56 evals READY. List real CRITICAL/HIGH only."
    echo "End with VERDICT: PASS or VERDICT: FAIL"
    head -60 "$C/reviews/INTEGRATE-FIXED-2143.md"
    git -C "$WT" diff --stat dff84e3...HEAD -- webchat/ | head -40
  } > "$SHORT"
  "$C/compat/ask-minimax.sh" -f "$SHORT" --out "$OUT_M" || python3 "$C/services/compat.py" minimax --tip -f "$SHORT" --out "$OUT_M" || true
fi
{
  echo "# INTEGRATE LIVE gate 2205 — $(date)"
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
    echo "GATE: FAIL tip=$NOW"
  fi
} > "$C/reviews/INTEGRATE-LIVE-2205.md"
echo "DONE $(date)"

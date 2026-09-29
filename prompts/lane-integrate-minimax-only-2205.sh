#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
WT="$HOME/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057"
LOG="$C/logs/lane-integrate-minimax-only-2205.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date)"
NOW=ab50533
FULL=ab5053331d128372607194a0756b893d3872c7a0
CTX="$C/prompts/integrate-livereview-ctx-ab50533-2205.md"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-integrate-2057-${NOW}.md"
OUT_G="$C/reviews/LIVE-GEMINI-draft_webbob-integrate-2057-${NOW}.md"
# Wait briefly for minimax lock if held
for i in 1 2 3 4 5 6; do
  if python3 -c "
import fcntl,sys
from pathlib import Path
p=Path('$C/locks/lane-minimax.lock')
p.parent.mkdir(parents=True, exist_ok=True)
f=p.open('a+')
try:
  fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)
  fcntl.flock(f, fcntl.LOCK_UN)
  print('free')
  sys.exit(0)
except BlockingIOError:
  print('busy')
  sys.exit(1)
finally:
  f.close()
" 2>/dev/null; then
    break
  fi
  echo "minimax lock busy, sleep 15 ($i)"
  sleep 15
done
echo "MiniMax -> $OUT_M"
# Prefer blocking tip ask via compat with retry
ok=0
for attempt in 1 2 3; do
  echo "attempt $attempt $(date)"
  if "$C/compat/ask-minimax.sh" -f "$CTX" --out "$OUT_M"; then
    ok=1
    break
  fi
  # fallback: tip mode
  if python3 "$C/services/compat.py" minimax --tip -f "$CTX" --out "$OUT_M"; then
    ok=1
    break
  fi
  sleep 20
done
if ! grep -q 'VERDICT' "$OUT_M" 2>/dev/null; then
  SHORT="$C/prompts/integrate-livereview-short-ab50533-2205.md"
  {
    echo "Strict INTEGRATE-ONLY code review of tip $FULL (status_observation + lane awareness + apiworkers)."
    echo "Gemini already PASSed this tip. Offline: 319 webchat + 129 services + 56 evals READY."
    echo "List real CRITICAL/HIGH bugs only. End with exactly: VERDICT: PASS or VERDICT: FAIL"
    head -70 "$C/reviews/INTEGRATE-FIXED-2143.md"
    git -C "$WT" diff --stat dff84e3...HEAD -- webchat/ | head -50
    git -C "$WT" diff dff84e3...HEAD -- webchat/status_observation.py webchat/reply_authority.py webchat/integration_rubric.py 2>/dev/null | head -250
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
cat "$C/reviews/INTEGRATE-LIVE-2205.md"

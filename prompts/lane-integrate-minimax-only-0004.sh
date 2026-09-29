#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
C="$HOME/Documents/bob-overnight-inject/conductor"
LOG="$C/logs/lane-integrate-minimax-only-0004.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date)"
NOW=2cdcce9
FULL=2cdcce928ea6a975825829a6c10a88a99017f643
CTX="$C/prompts/integrate-livereview-short-2cdcce9-0004.md"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-integrate-2057-${NOW}.md"
OUT_G="$C/reviews/LIVE-GEMINI-draft_webbob-integrate-2057-${NOW}.md"
# wait for minimax lock
for i in 1 2 3 4 5 6 7 8; do
  if python3 -c "
import fcntl,sys
from pathlib import Path
p=Path('$C/locks/lane-minimax.lock')
p.parent.mkdir(parents=True, exist_ok=True)
f=p.open('a+')
try:
  fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)
  fcntl.flock(f, fcntl.LOCK_UN)
  print('free'); sys.exit(0)
except BlockingIOError:
  print('busy'); sys.exit(1)
finally:
  f.close()
" 2>/dev/null; then
    break
  fi
  echo "minimax lock busy, sleep 20 ($i)"
  sleep 20
done
echo "MiniMax -> $OUT_M"
ok=0
for attempt in 1 2 3 4; do
  echo "attempt $attempt $(date)"
  if [ -x "$C/compat/ask-minimax.sh" ]; then
    if "$C/compat/ask-minimax.sh" -f "$CTX" --out "$OUT_M"; then ok=1; break; fi
  fi
  if python3 "$C/services/compat.py" minimax --tip -f "$CTX" --out "$OUT_M"; then ok=1; break; fi
  sleep 25
done
echo "ask_ok=$ok"
grep -E 'VERDICT' "$OUT_M" 2>/dev/null | tail -5 || echo '(no VERDICT yet)'
{
  echo "# INTEGRATE LIVE gate 0004 — $(date)"
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
    echo "GATE: NOT_BOTH_PASS tip=$NOW"
  fi
} > "$C/reviews/INTEGRATE-LIVE-0004.md"
cp "$C/reviews/INTEGRATE-LIVE-0004.md" "$C/reviews/INTEGRATE-LIVE-2305.md" 2>/dev/null || true
echo "DONE $(date)"
cat "$C/reviews/INTEGRATE-LIVE-0004.md"

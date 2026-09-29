#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export BOB_ROOT="$HOME/Documents/bob-overnight-inject"
C="$BOB_ROOT/conductor"
LOG="$C/logs/lane-gaps-minimax-0204.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date) marker=0204 gaps tip=953f440 MiniMax LIVE with patch evidence"
PROMPT="$C/reviews/PROMPT-gaps-live-0204.md"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-gaps-1725-953f440-0204.md"
OUT_CANON="$C/reviews/LIVE-MINIMAX-draft_webbob-gaps-1725-953f440.md"
# wait for minimax lock
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
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
ok=0
for attempt in 1 2 3 4 5; do
  echo "attempt $attempt $(date) prompt_bytes=$(wc -c < "$PROMPT")"
  if "$C/compat/ask-minimax.sh" -f "$PROMPT" --out "$OUT_M"; then ok=1; break; fi
  if python3 "$C/services/compat.py" minimax --tip -f "$PROMPT" --out "$OUT_M"; then ok=1; break; fi
  sleep 30
done
echo "ask_ok=$ok"
# if empty, write diagnostic
if [ ! -s "$OUT_M" ] || ! grep -q 'VERDICT' "$OUT_M" 2>/dev/null; then
  echo "no VERDICT; file size=$(wc -c < "$OUT_M" 2>/dev/null || echo 0)"
fi
cp -f "$OUT_M" "$OUT_CANON" 2>/dev/null || true
grep -E 'VERDICT' "$OUT_M" 2>/dev/null | tail -5 || echo '(no VERDICT yet)'
{
  echo "# GAPS MiniMax LIVE 0204 — $(date)"
  echo "tip: 953f440"
  echo "full: 953f4402b8049b877bcf6fd0bfd8b94e22aaae70"
  echo "prompt: $PROMPT"
  echo "out: $OUT_M"
  echo "ask_ok: $ok"
  echo
  grep -E 'VERDICT' "$OUT_M" 2>/dev/null | tail -5 || echo '(missing VERDICT)'
} > "$C/reviews/GAPS-MINIMAX-LIVE-0204.md"
echo "DONE $(date)"
cat "$C/reviews/GAPS-MINIMAX-LIVE-0204.md"

#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export BOB_ROOT="$HOME/Documents/bob-overnight-inject"
C="$BOB_ROOT/conductor"
WT="$BOB_ROOT/workspaces/webbob-integrate-2057"
LOG="$C/logs/lane-integrate-livereview-0256.log"
exec >>"$LOG" 2>&1
set -a
[ -f "$C/keys.env" ] && . "$C/keys.env"
[ -f "$HOME/.bob-keys" ] && . "$HOME/.bob-keys"
set +a
echo "START $(date) marker=0256 tip=199eb19"
NOW=$(git -C "$WT" rev-parse --short HEAD)
FULL=$(git -C "$WT" rev-parse HEAD)
echo "tip $NOW $FULL"
if [ "$FULL" != "199eb193396802bbbf899292e48cd04a55f9c57e" ]; then
  echo "WARN tip mismatch expected 199eb19 got $FULL — reviewing actual tip"
fi
CTX="$C/prompts/integrate-livereview-ctx-199eb19-0256.md"
SHORT="$C/prompts/integrate-livereview-short-199eb19-0256.md"
OUT_G="$C/reviews/LIVE-GEMINI-draft_webbob-integrate-2057-${NOW}-0256.md"
OUT_M="$C/reviews/LIVE-MINIMAX-draft_webbob-integrate-2057-${NOW}-0256.md"
# also write canonical names without -0256 for gate scripts
OUT_G_CANON="$C/reviews/LIVE-GEMINI-draft_webbob-integrate-2057-${NOW}.md"
OUT_M_CANON="$C/reviews/LIVE-MINIMAX-draft_webbob-integrate-2057-${NOW}.md"

wait_lock() {
  local name="$1"
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if python3 -c "
import fcntl,sys
from pathlib import Path
p=Path('$C/locks/lane-${name}.lock')
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
      return 0
    fi
    echo "${name} lock busy, sleep 15 ($i)"
    sleep 15
  done
  return 0
}

echo "Gemini -> $OUT_G"
wait_lock gemini || true
ok_g=0
for attempt in 1 2 3; do
  echo "gemini attempt $attempt $(date)"
  if "$C/compat/ask-gemini.sh" -f "$CTX" --out "$OUT_G"; then ok_g=1; break; fi
  if python3 "$C/services/compat.py" gemini --tip -f "$CTX" --out "$OUT_G"; then ok_g=1; break; fi
  sleep 20
done
echo "gemini_ok=$ok_g"
cp -f "$OUT_G" "$OUT_G_CANON" 2>/dev/null || true
grep -E 'VERDICT' "$OUT_G" 2>/dev/null | tail -5 || echo '(no gemini VERDICT yet)'

echo "MiniMax -> $OUT_M"
wait_lock minimax || true
ok_m=0
for attempt in 1 2 3 4; do
  echo "minimax attempt $attempt $(date)"
  PROMPT_USE="$CTX"
  [ "$attempt" -ge 3 ] && PROMPT_USE="$SHORT"
  if "$C/compat/ask-minimax.sh" -f "$PROMPT_USE" --out "$OUT_M"; then ok_m=1; break; fi
  if python3 "$C/services/compat.py" minimax --tip -f "$PROMPT_USE" --out "$OUT_M"; then ok_m=1; break; fi
  sleep 25
done
echo "minimax_ok=$ok_m"
# if still no VERDICT, try short once more
if ! grep -q 'VERDICT' "$OUT_M" 2>/dev/null; then
  echo "minimax retry short $(date)"
  "$C/compat/ask-minimax.sh" -f "$SHORT" --out "$OUT_M" || python3 "$C/services/compat.py" minimax --tip -f "$SHORT" --out "$OUT_M" || true
fi
cp -f "$OUT_M" "$OUT_M_CANON" 2>/dev/null || true
grep -E 'VERDICT' "$OUT_M" 2>/dev/null | tail -5 || echo '(no minimax VERDICT yet)'

{
  echo "# INTEGRATE LIVE gate 0256 — $(date)"
  echo "tip: $NOW"
  echo "full: $FULL"
  echo "gemini_out: $OUT_G"
  echo "minimax_out: $OUT_M"
  echo "marker: 0256 / 199eb19"
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
} > "$C/reviews/INTEGRATE-LIVE-0256.md"
cp "$C/reviews/INTEGRATE-LIVE-0256.md" "$C/reviews/INTEGRATE-LIVE-199eb19.md" 2>/dev/null || true
echo "DONE $(date)"
cat "$C/reviews/INTEGRATE-LIVE-0256.md"

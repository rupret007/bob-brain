#!/bin/bash
# Double-click to take over from Bob. Restarts the mini loop if needed, then opens Claude (or Codex) as Bob.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
B="$HOME/Documents/bob-overnight-inject"
cd "$B" || { echo "Missing $B"; read -r; exit 1; }
[ -f conductor/keys.env ] && . conductor/keys.env
(cd bob-brain 2>/dev/null && git pull -q 2>/dev/null)
if [ -x conductor/services/start-all.sh ]; then bash conductor/services/start-all.sh
elif ! screen -ls | grep -q mini-conductor; then screen -dmS mini-conductor bash conductor/loop.sh; fi
echo "=== Running services ==="; screen -ls | grep -E 'svc-|mini-conductor'
echo; echo "=== STATUS ==="; [ -f conductor/STATUS.md ] && head -40 conductor/STATUS.md
echo; echo "Starting Bob stand-in..."
P="Read BOB-HANDOFF.md and act as Bob, Jeff's conductor. Use bob-brain/ for skills and memory. Check conductor/STATUS.md and tell me what needs me."
if command -v claude >/dev/null; then claude "$P"; else codex "$P"; fi

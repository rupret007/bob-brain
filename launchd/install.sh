#!/bin/bash
# Run in Terminal after granting Full Disk Access to /bin/bash.
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS" "$ROOT/conductor/launchd/retired"
for label in com.jeff.mini-conductor com.jeff.mini-tick; do
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  if [ -f "$AGENTS/$label.plist" ]; then
    cp "$AGENTS/$label.plist" "$ROOT/conductor/launchd/retired/$label.plist"
    rm "$AGENTS/$label.plist"
  fi
done
for label in com.jeff.bob-services com.jeff.bob-watchdog; do
  cp "$ROOT/conductor/launchd/$label.plist" "$AGENTS/$label.plist"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$AGENTS/$label.plist"
done
/bin/bash "$ROOT/conductor/services/start-all.sh"
printf 'Installed both LaunchAgents for login after reboot. Keep Full Disk Access enabled for /bin/bash.\n'

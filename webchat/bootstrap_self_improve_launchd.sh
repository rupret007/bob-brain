#!/usr/bin/env bash
# One-time on the mini: load Web Bob self-improve tick (draft branch only, no Grok).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST_SRC="$ROOT/conductor/launchd/com.jeff.bob-webchat-self-improve.plist"
LABEL="com.jeff.bob-webchat-self-improve"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
if [[ ! -f "$PLIST_SRC" ]]; then
  echo "Missing $PLIST_SRC" >&2
  exit 1
fi
chmod +x "$ROOT/conductor/webchat/self_improve_tick.sh"
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/logs"
cp "$PLIST_SRC" "$DEST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
launchctl enable "gui/$(id -u)/$LABEL"
echo "Loaded $LABEL — logs: $ROOT/logs/webchat-self-improve.log"

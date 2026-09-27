#!/bin/bash
set -eu
umask 077
WEBCHAT_DIR="$(cd "$(dirname "$0")" && pwd)"
export BOB_ROOT="${BOB_ROOT:-$(cd "$WEBCHAT_DIR/../.." && pwd)}"
export BOB_WEBCHAT_DIR="$BOB_ROOT/conductor/webchat"
BOB_CODE_ROOT="$BOB_ROOT/conductor"
if [ -f "$BOB_ROOT/conductor/state/dispatch-code-root" ]; then
  IFS= read -r BOB_CODE_ROOT < "$BOB_ROOT/conductor/state/dispatch-code-root"
fi
export BOB_CODE_ROOT
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export BOB_WEBCHAT_DRILLS="${BOB_WEBCHAT_DRILLS:-0}"
mkdir -p "$BOB_ROOT/logs"
cd "$BOB_ROOT"
set -a
[ ! -f "$BOB_ROOT/conductor/keys.env" ] || . "$BOB_ROOT/conductor/keys.env"
set +a
exec python3 -u "$BOB_CODE_ROOT/webchat/app.py" < /dev/null >> "$BOB_ROOT/logs/webchat-server.log" 2>&1

#!/bin/bash
set -eu
umask 077
WEBCHAT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOB_ROOT="$(cd "$WEBCHAT_DIR/../.." && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
mkdir -p "$BOB_ROOT/logs"
cd "$BOB_ROOT"
exec python3 -u "$WEBCHAT_DIR/app.py" < /dev/null >> "$BOB_ROOT/logs/webchat-server.log" 2>&1

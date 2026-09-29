#!/bin/bash
set -eu
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
WEBCHAT_DIR="$(cd "$(dirname "$0")" && pwd)"
export BOB_ROOT="${BOB_ROOT:-$(cd "$WEBCHAT_DIR/../.." && pwd)}"
if [ -f "$BOB_ROOT/conductor/state/webchat-code-root" ]; then
  IFS= read -r BOB_WEBCHAT_CODE_ROOT < "$BOB_ROOT/conductor/state/webchat-code-root"
  WEBCHAT_DIR="$BOB_WEBCHAT_CODE_ROOT/webchat"
  export BOB_WEBCHAT_DISPATCH=1
  if [ "${BOB_WEBCHAT_DRILLS:-}" != "1" ]; then
    export BOB_WEBCHAT_DRILLS=0
  fi
fi
exec python3 "$WEBCHAT_DIR/start.py"

#!/bin/bash
set -eu
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
WEBCHAT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$WEBCHAT_DIR/start.py"

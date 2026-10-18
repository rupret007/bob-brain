#!/bin/bash
# Compatibility only: the four services own all timers and launches.
export BOB_ROOT="${BOB_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
exec python3 "$BOB_ROOT/conductor/bootstrap.py" runtime legacy-shim < /dev/null

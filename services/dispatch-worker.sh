#!/bin/bash
set -eu
umask 077
export BOB_ROOT="${BOB_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
export BOB_CODE_ROOT="${BOB_CODE_ROOT:-$BOB_ROOT/conductor}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
set -a
[ ! -f "$BOB_ROOT/conductor/keys.env" ] || . "$BOB_ROOT/conductor/keys.env"
set +a
mkdir -p "$BOB_ROOT/conductor/state/task-runs/$1"
exec python3 "$BOB_CODE_ROOT/services/dispatch_worker.py" "$1" "$2" \
  < /dev/null >> "$BOB_ROOT/conductor/state/task-runs/$1/worker.log" 2>&1

#!/bin/bash
set -e
export BOB_ROOT="${BOB_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
set -a
[ -f "$BOB_ROOT/conductor/keys.env" ] && . "$BOB_ROOT/conductor/keys.env"
set +a
if [ "${1:-}" = "--ux-pass" ]; then
  shift
  exec python3 "$BOB_ROOT/conductor/webjam-ux/paid_review.py" "$@" < /dev/null
fi
exec python3 "$BOB_ROOT/conductor/services/compat.py" minimax "$@"

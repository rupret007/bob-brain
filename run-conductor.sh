#!/bin/bash
export BOB_ROOT="${BOB_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$BOB_ROOT" || exit 1
set -a
[ -f conductor/keys.env ] && . conductor/keys.env
set +a
mkdir -p logs
exec python3 conductor/services/conductor_pass.py >> logs/conductor.log 2>&1

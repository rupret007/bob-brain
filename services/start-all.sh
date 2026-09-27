#!/bin/bash
export BOB_ROOT="${BOB_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$BOB_ROOT" || exit 1
mkdir -p logs conductor/heartbeats
exec python3 conductor/services/runtime.py start-all "$@" >> logs/start-all.log 2>&1

#!/bin/bash
# usage: council.sh [--context FILE_OR_DIR ...] "question"   (transcript -> conductor/council/<ts>.md)
export BOB_ROOT="${BOB_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$BOB_ROOT" || exit 1
mkdir -p logs conductor/council
set -a
[ -f conductor/keys.env ] && . conductor/keys.env
set +a
exec python3 conductor/bootstrap.py council "$@" < /dev/null 2>> logs/council.log

#!/bin/bash
set -e
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
exec python3 "$(cd "$(dirname "$0")" && pwd)/install.py" < /dev/null

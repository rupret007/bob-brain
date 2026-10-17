#!/bin/bash
set -euo pipefail
CODE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Run discovery separately: both directories contain a test_dispatch.py.
(cd "$CODE_ROOT/webchat" && python3 -m pytest -q --tb=short)
(cd "$CODE_ROOT/services" && python3 -m pytest -q --tb=short)
node "$CODE_ROOT/webchat/test_quiet_hours_js.mjs"
node --test "$CODE_ROOT/webchat/test_reply_playback.cjs"
node --check "$CODE_ROOT/webchat/static/app.js"
node --check "$CODE_ROOT/webchat/static/reply-playback.js"
node --check "$CODE_ROOT/webchat/test_media_browser.cjs"
python3 "$CODE_ROOT/webchat/media_browser_test.py"
python3 -m py_compile "$CODE_ROOT/bootstrap.py"
git -C "$CODE_ROOT" diff --check

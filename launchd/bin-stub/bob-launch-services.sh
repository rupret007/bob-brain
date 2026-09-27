#!/bin/bash
# Installed to ~/bin by launchd/install.py. launchd must not execute scripts under ~/Documents.
set -eu
BOB_ROOT="@@BOB_ROOT@@"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$HOME" || cd /
exec /bin/bash "$BOB_ROOT/conductor/services/start-all.sh" "$@"

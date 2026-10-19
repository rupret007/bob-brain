#!/bin/bash
# chain.sh HOOK [ARGS...]  (lane-ops v3) — lane runs set core.hooksPath to this folder through GIT_CONFIG_* env
# (lane-supervise.sh). That env setting hides the repo's own hooks (husky etc.), so every hook here hands off to
# the repo's hook of the same name afterwards: `git config --local core.hooksPath`, else <git-common-dir>/hooks.
H=$1; shift
me=$(cd "$(dirname "$0")" && pwd -P)
hp=$(git config --local --get core.hooksPath 2>/dev/null)
if [ -n "$hp" ]; then case $hp in /*) ;; *) hp="$(git rev-parse --show-toplevel 2>/dev/null)/$hp";; esac
else hp="$(git rev-parse --git-common-dir 2>/dev/null)/hooks"; fi
d=$(cd "$hp" 2>/dev/null && pwd -P) || exit 0
[ "$d" = "$me" ] && exit 0
[ -x "$d/$H" ] && exec "$d/$H" "$@"
exit 0

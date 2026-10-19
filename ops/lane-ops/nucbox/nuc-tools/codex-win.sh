#!/bin/bash
# Invoke the Windows Codex desktop CLI from WSL using the existing Windows sign-in.
# Never reads/copies/prints/modifies auth.json. Never login/logout.
# ChatGPT-account-compatible model: gpt-6-astra (Windows config default gpt-5.4 is NOT supported).
# lane-ops v3 (arch-review-2 B8): pick by the VERSION codex.exe reports (`--version`, highest per sort -V), not by the
# newest bin/ mtime. The bin/ dirs are content hashes, so mtime was the only signal and a half-installed update could
# be picked mid-install. A dir modified in the last CODEX_MIN_AGE_S seconds (default 300: still unpacking) or whose
# codex.exe does not answer --version is skipped.
# `codex-win.sh --which` prints the chosen codex.exe and exits 0 (used by lane-route.sh nuc_codex_ok).
set -euo pipefail
BIN_ROOT="${CODEX_BIN_ROOT:-/mnt/c/Users/rupret/AppData/Local/OpenAI/Codex/bin}"
MIN_AGE=${CODEX_MIN_AGE_S:-300}
CODEX_EXE=""
if [ -d "$BIN_ROOT" ]; then
  now=$(date +%s); cands=""
  for dir in "$BIN_ROOT"/*/; do
    dir=${dir%/}; exe="$dir/codex.exe"
    [ -x "$exe" ] || continue
    m=$(stat -c %Y "$dir" 2>/dev/null || echo "$now"); fm=$(stat -c %Y "$exe" 2>/dev/null || echo "$now")
    [ "$fm" -gt "$m" ] && m=$fm
    [ $(( now - m )) -ge "$MIN_AGE" ] || continue
    v=$(timeout "${CODEX_PROBE_TIMEOUT:-20}" "$exe" --version 2>/dev/null </dev/null | grep -oE '[0-9]+(\.[0-9]+)+([.-][A-Za-z0-9.]+)?' | head -1) || v=
    [ -n "$v" ] || continue
    cands+="$v"$'\t'"$exe"$'\n'
  done
  CODEX_EXE=$(printf '%s' "$cands" | sort -t$'\t' -k1,1V | tail -1 | cut -f2)
fi
if [ -z "${CODEX_EXE}" ]; then
  echo "BLOCKER: no settled, working codex.exe under $BIN_ROOT" >&2
  exit 2
fi
if [ "${1:-}" = "--which" ]; then echo "$CODEX_EXE"; exit 0; fi
MODEL="${CODEX_MODEL:-gpt-6-astra}"
# Force model on every call so a stale Windows config default cannot break lanes.
exec "$CODEX_EXE" -m "$MODEL" "$@"

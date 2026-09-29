#!/bin/bash
# Bash 3.2 compatible. No GNU timeout, flock executable, jq, or rg required.
service_loop() {
  local name="$1" interval="$2"
  shift 2
  export BOB_ROOT="${BOB_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
  export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
  mkdir -p "$BOB_ROOT/logs" "$BOB_ROOT/conductor/heartbeats"
  cd "$BOB_ROOT" || return 1
  local code_root="$BOB_ROOT/conductor"
  [ "$name" != "job-runner" ] || code_root="${BOB_CODE_ROOT:-$code_root}"
  if [ "${1:-}" != "--locked" ]; then
    exec python3 "$code_root/bootstrap.py" runtime lock-service "$name" "$@"
  fi
  shift
  exec >> "$BOB_ROOT/logs/$name.log" 2>&1
  local once=0 child="" rc=0
  [ "${1:-}" = "--once" ] && once=1
  trap 'trap - HUP INT TERM; [ -n "$child" ] && kill -TERM "$child" 2>/dev/null; wait "$child" 2>/dev/null; exit 0' HUP INT TERM
  while true; do
    # Reload rotated credentials every cycle. Never trace or print the keys.
    set -a
    [ -f conductor/keys.env ] && . conductor/keys.env
    set +a
    python3 "$code_root/bootstrap.py" runtime cycle "$name" < /dev/null &
    child=$!
    wait "$child"
    rc=$?
    child=""
    if [ "$rc" -ne 0 ]; then
      printf '%s cycle failed rc=%s; loop continues\n' "$name" "$rc"
    fi
    [ "$once" -eq 1 ] && return "$rc"
    sleep "$interval" &
    child=$!
    wait "$child"
    child=""
  done
}

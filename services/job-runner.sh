#!/bin/bash
export BOB_ROOT="${BOB_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
BOB_CODE_ROOT="${BOB_CODE_ROOT:-$BOB_ROOT/conductor}"
if [ -f "$BOB_ROOT/conductor/state/dispatch-code-root" ]; then
  IFS= read -r BOB_CODE_ROOT < "$BOB_ROOT/conductor/state/dispatch-code-root"
fi
export BOB_CODE_ROOT
if [ "$(cd "$(dirname "$0")/.." && pwd)" != "$BOB_CODE_ROOT" ]; then
  exec /bin/bash "$BOB_CODE_ROOT/services/job-runner.sh" "$@"
fi
. "$BOB_CODE_ROOT/services/common.sh"
service_loop job-runner 5 "$@"

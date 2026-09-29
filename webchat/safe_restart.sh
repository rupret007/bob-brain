#!/bin/bash
# Gentle deploy restart: defer while replies are in flight or inside the 30m batch window.
set -eu
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
WEBCHAT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$WEBCHAT_DIR/../.." && pwd)"
REASON="${1:-round deploy}"
cd "$ROOT"
python3 - <<'PY' "$REASON"
import sys
import os
import signal
import subprocess
import time
from pathlib import Path

root = Path(".").resolve()
reason = sys.argv[1]
try:
    import deploy_restart as dr
except ImportError:
    sys.path.insert(0, str(root / "conductor/webchat"))
    import deploy_restart as dr

from live_failover import Curl

try:
    client = Curl("http://127.0.0.1:8787")
    try:
        verdict = dr.authenticated_verdict(client.json("/api/panel"))
    finally:
        client.close()
except Exception:
    raise SystemExit("Restart deferred: authenticated chat status is unavailable.") from None
dr.append_restart_event(root, reason, deferred=not verdict["allowed"], defer_reasons=verdict.get("defer_reasons") or [])
if not verdict["allowed"]:
    print("Deferring webchat restart:", ", ".join(verdict["defer_reasons"]))
    dr.record_restart(root, reason, deferred=True)
    sys.exit(2)
dr.record_restart(root, reason, deferred=False)
result = subprocess.run(["lsof", "-t", "-iTCP:8787", "-sTCP:LISTEN"], capture_output=True, text=True, check=True)
pids = set(result.stdout.split())
if len(pids) != 1:
    raise SystemExit("Restart deferred: expected exactly one webchat listener.")
pid = int(next(iter(pids)))
command = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=True).stdout
if str(root / "conductor/webchat/app.py") not in command:
    raise SystemExit("Restart deferred: listener does not match webchat.")
os.kill(pid, signal.SIGTERM)
for _ in range(60):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        break
    time.sleep(.25)
else:
    raise SystemExit("Restart deferred: webchat is still shutting down.")
PY
bash "$WEBCHAT_DIR/start.sh"

#!/usr/bin/env python3
"""Opt-in Stop drill: a harmless sleeping child and a nested process group."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

if os.environ.get("BOB_WEBCHAT_DRILLS") != "1":
    raise SystemExit("Drills are disabled")

children = [subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"],
                            stdin=subprocess.DEVNULL, start_new_session=detached)
            for detached in (False, True)]
path = Path(sys.argv[1])
path.write_text(json.dumps({"parent": os.getpid(), "children": [p.pid for p in children]}))
path.chmod(0o600)
time.sleep(600)

#!/usr/bin/env python3
"""Compatibility: only the service scheduler launches jobs."""
import os,sys
from pathlib import Path
root=Path(os.environ.get("BOB_ROOT",Path(__file__).resolve().parents[1]))
os.execv(sys.executable,[sys.executable,str(root/"conductor/bootstrap.py"),"runtime","legacy-shim"])

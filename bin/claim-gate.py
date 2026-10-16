#!/usr/bin/env python3
"""Staged successor. Does not replace the running conductor's script."""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
runpy.run_module("webbob.ownership", run_name="__main__")

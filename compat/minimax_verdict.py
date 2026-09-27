#!/usr/bin/env python3
"""Compatibility tip review; share the conductor lane and spending guard."""
import os,sys
from pathlib import Path
root=Path(os.environ.get("BOB_ROOT",Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(root/"conductor/services"))
from compat import main
if __name__=="__main__":raise SystemExit(main(["minimax","--tip","-f",sys.argv[1]]))

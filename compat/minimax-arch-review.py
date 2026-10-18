#!/usr/bin/env python3
"""Bounded metered architecture review of the current core."""
import os,sys
from pathlib import Path
root=Path(os.environ.get("BOB_ROOT",Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(root/"conductor/services"))
from lanes import ask
from state import atomic_write
parts=[]
for name in ["PROMPT.md","services/jobs.py","services/worker.py","services/runtime.py","services/budget.py"]:
 p=root/"conductor"/name
 if p.exists():parts.append(name+"\n"+p.read_text()[:20000])
text=ask("minimax","Review this architecture: give evidence and ranked concrete fixes.\n"+"\n\n".join(parts),purpose="architecture-review")
atomic_write(root/"conductor/reviews/LATEST-MINIMAX.md",text+"\n")
print(text)

#!/usr/bin/env python3
"""Legacy interface; paid requests now use the conductor's shared lane/ledger."""
import os,sys
from pathlib import Path
ROOT=Path(os.environ.get("BOB_ROOT",Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(ROOT/"conductor/services"))
from lanes import ask
from api import MODELS
from compat import main as compatible_main

def call(provider,prompt,env=None,**kwargs):
    answer=ask(provider,prompt,purpose="legacy-helper")
    return answer,False,MODELS[provider]

def main(argv=None):
    return compatible_main((argv or sys.argv)[1:])

if __name__=="__main__":raise SystemExit(main())

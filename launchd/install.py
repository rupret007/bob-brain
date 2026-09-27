#!/usr/bin/env python3
"""Install the Mini's one supervisor and watchdog guard with bounded commands."""
import os
import shutil
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services'))
from command import run
from state import CONDUCTOR,ROOT

def main():
    agents=Path.home()/'Library/LaunchAgents'
    agents.mkdir(parents=True,exist_ok=True)
    retired=CONDUCTOR/'launchd/retired';retired.mkdir(exist_ok=True)
    domain='gui/'+str(os.getuid())
    for label in ('com.jeff.mini-conductor','com.jeff.mini-tick'):
        run(['launchctl','bootout',domain+'/'+label],capture_output=True,timeout=15)
        old=agents/(label+'.plist')
        if old.exists():shutil.copy2(old,retired/old.name);old.unlink()
    for label in ('com.jeff.bob-services','com.jeff.bob-watchdog'):
        source=CONDUCTOR/'launchd'/(label+'.plist');target=agents/source.name
        run(['plutil','-lint',str(source)],capture_output=True,timeout=15,check=True)
        shutil.copy2(source,target)
        run(['launchctl','bootout',domain+'/'+label],capture_output=True,timeout=15)
        run(['launchctl','bootstrap',domain,str(target)],capture_output=True,timeout=30,check=True)
        run(['launchctl','print',domain+'/'+label],capture_output=True,timeout=15,check=True)
        print('Installed and loaded '+label,flush=True)
    run(['/bin/bash',str(CONDUCTOR/'services/start-all.sh')],timeout=60,check=True)

if __name__=='__main__':main()

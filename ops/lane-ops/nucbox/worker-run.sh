#!/bin/bash
cd $HOME/work/bob-ops-dashboard
export PYTHONPATH=.:$HOME/.local/share/bob-cluster-py
exec python3 cluster/worker.py --node-id nucbox --token-file $HOME/.config/bob-cluster/nucbox.env --classes test,build,render --max-parallel 2 >> $HOME/.config/bob-cluster/worker.log 2>&1

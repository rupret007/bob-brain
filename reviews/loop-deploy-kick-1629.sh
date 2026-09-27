#!/bin/bash
# Run the real discovered suites and the authenticated, rollback-gated deploy.
set -euo pipefail
BASE="$HOME/Documents/bob-overnight-inject"
WT="$BASE/workspaces/webbob-parity-1633"
PR="${1:?Pass the open draft PR URL for this candidate}"
bash "$WT/reviews/run-webbob-tests.sh" 2>&1 | tee "$BASE/conductor/reviews/WEBBOB-PARITY-TESTS-0927.txt"
python3 "$WT/webchat/deploy_parity.py" --root "$BASE" --candidate "$WT" --draft-pr "$PR"

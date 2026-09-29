#!/bin/bash
set -euo pipefail
umask 077
export BOB_ROOT="/Users/jeffstory/Documents/bob-overnight-inject"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export TMPDIR=/private/tmp
export PYTHONPATH="$BOB_ROOT/workspaces/webbob-texting-onto-a777736-0420/webchat"
TEXTING_DEPLOY_LOG="$BOB_ROOT/conductor/reviews/TEXTING-DEPLOY-0702.log"
exec > >(tee -a "$TEXTING_DEPLOY_LOG") 2>&1
exec python3 -u "$BOB_ROOT/conductor/reviews/record_texting_deploy_0702.py"

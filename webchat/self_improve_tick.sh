#!/usr/bin/env bash
# Web Bob self-improvement tick (no Grok): tests + handback note. Draft branch only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
LOG="$ROOT/conductor/handback/HANDBACK-LOG.md"
STAMP="$(TZ=America/Chicago date '+%Y-%m-%d %H:%M:%S CT')"
BRANCH="$(git -C "$ROOT/conductor" branch --show-current 2>/dev/null || echo unknown)"
if [[ "$BRANCH" != draft/* ]]; then
  echo "self-improve tick skipped: not on draft branch ($BRANCH)" >&2
  exit 0
fi
WEBCHAT_RC=0
FAILOVER_RC=0
python3 conductor/webchat/test_webchat.py >/tmp/webchat-self-improve-tests.txt 2>&1 || WEBCHAT_RC=$?
python3 conductor/webchat/test_failover.py >>/tmp/webchat-self-improve-tests.txt 2>&1 || FAILOVER_RC=$?
SHA="$(git -C "$ROOT/conductor" rev-parse HEAD 2>/dev/null || echo unknown)"
{
  echo "## $STAMP"
  echo "- **Ask:** webchat self-improve tick"
  echo "- **Provider:** local"
  echo "- **Commits/SHAs:** $SHA"
  echo "- **Open:** review /tmp/webchat-self-improve-tests.txt on mini if failures"
  if [[ "$WEBCHAT_RC" -ne 0 || "$FAILOVER_RC" -ne 0 ]]; then
    echo "- **Outcome:** error"
  else
    echo "- **Outcome:** chat"
  fi
  echo ""
} >>"$LOG"
python3 -c "import sys; from pathlib import Path; sys.path.insert(0, '$ROOT/conductor/webchat'); from handback import refresh_summary; refresh_summary(Path('$ROOT'))"
if [[ "$WEBCHAT_RC" -ne 0 || "$FAILOVER_RC" -ne 0 ]]; then
  echo "self-improve tests failed (webchat=$WEBCHAT_RC failover=$FAILOVER_RC)" >&2
  exit 1
fi

#!/bin/bash
# Double-click to take over from Bob. Shows the live state, starts the four services if it is safe,
# then opens Claude (or Codex) as the Bob stand-in with BOB-HANDOFF.md.
# BOB_TAKEOVER_DRYRUN=1  -> read-only diagnostics, no pull / service start / agent launch (for testing).
# BOB_FORCE_START=1      -> start services even though conductor/MAINTENANCE exists.
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"  # append: a double-click has a minimal PATH; callers/tests can still override
B="${BOB_ROOT:-$HOME/Documents/bob-overnight-inject}"
DRY="${BOB_TAKEOVER_DRYRUN:-0}"
pause() { [ "$DRY" = 1 ] || read -r; }
cd "$B" || { echo "Missing $B"; pause; exit 1; }
# NOTE: keys.env is deliberately NOT sourced here; the bin/ and conductor/ scripts load it themselves.

echo "=== Bob brain ==="
if [ "$DRY" = 1 ]; then echo "(dry run: skipping pull)"
elif [ -d bob-brain/.git ]; then git -C bob-brain pull --ff-only 2>&1 | tail -2 || echo "WARN: bob-brain pull failed; using local copy"
else echo "WARN: bob-brain/ missing"; fi
[ -f bin/build-skill-index.py ] && [ -d bob-brain/skills ] && [ "$DRY" != 1 ] && python3 bin/build-skill-index.py | tail -1

echo; echo "=== Services ==="
if [ -f conductor/MAINTENANCE ] && [ "${BOB_FORCE_START:-0}" != 1 ]; then
  echo "MAINTENANCE is set: $(head -c 200 conductor/MAINTENANCE)"
  echo "Not starting services (someone is mid-change). Ask Jeff, or rerun with BOB_FORCE_START=1."
elif [ "$DRY" = 1 ]; then echo "(dry run: would run conductor/services/start-all.sh)"
elif [ -f conductor/services/start-all.sh ]; then
  bash conductor/services/start-all.sh || echo "WARN: start-all.sh failed (see logs/start-all.log). NOT falling back to loop.sh (retired)."
else echo "WARN: conductor/services/start-all.sh missing"; fi
screen -ls 2>/dev/null | grep -E 'svc-' || echo "(no svc-* screens running)"

echo; echo "=== Agents (bin/who-is-running.sh) ==="
[ -x bin/who-is-running.sh ] && bin/who-is-running.sh 2>&1 | head -25 || echo "(who-is-running.sh missing)"

echo; echo "=== STATUS ==="
[ -f conductor/STATUS.md ] && head -40 conductor/STATUS.md || echo "(no STATUS.md)"

echo; echo "=== Preflight ==="
gh auth status >/dev/null 2>&1 && echo "gh: logged in" || echo "WARN: gh not logged in (PR/CI checks will be stale; Jeff must log in)"
python3 bin/check-handoff.py 2>&1 | tail -3

P="Read BOB-HANDOFF.md and act as Bob, Jeff's conductor. Follow its HARD RULES and the FIRST 2 MINUTES list, use BOB-SKILL-INDEX.md and bob-brain/ for skills and memory, then tell me in 5 lines or fewer what needs me."
echo
if [ "$DRY" = 1 ]; then
  if command -v codex >/dev/null; then echo "(dry run) would run: codex \"$P\""
  elif command -v claude >/dev/null; then echo "(dry run) would run: claude \"$P\""
  else echo "(dry run) neither claude nor codex found"; fi
  exit 0
fi
echo "Starting Bob stand-in..."
if command -v codex >/dev/null; then codex "$P"
elif command -v claude >/dev/null; then claude "$P"
else echo "Neither claude nor codex is installed."; pause; fi

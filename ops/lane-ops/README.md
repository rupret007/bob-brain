# lane-ops

The lane system (Mini fill loop, Gemini lanes, NucBox runners, claim gate) under git, so changes go
through a draft PR and Karen instead of being hand-edited live. Private on purpose: these files name
hosts, ports, paths and guard logic.

- `mini/lane-wt-logs/` -> `~/lane-wt/logs/` on the Mac mini
- `mini/bin/` -> `~/bin/` on the Mini (`claim-gate.py` -> `~/Documents/bob-overnight-inject/bin/`)
- `nucbox/` -> the NucBox WSL user `rupret` (`~/nuc-tools`, `~/bin`, `~/.config/...`)
- `MANIFEST.tsv` is the exact repo-path -> host -> live-path map. `tests/test_lane_ops.py` fails if
  a file is added without a manifest row.
- `tools/drift-check.sh` (read-only) prints OK / DRIFT / MISSING for every file against the live
  hosts. Run it in every self-improvement round; any DRIFT means a hand edit bypassed review.

## Rules
1. Edit here, open a draft PR, Karen gates, then deploy with the steps in `DEPLOY.md`.
2. Live hot-fixes are allowed only to stop damage; the same change must land here within the hour.
3. No secrets: keys stay in `conductor/keys.env` and `~/.config/bob-cluster/*.env` (tests scan for them).
4. Never loosen tests; `gat-policy.py` enforces this for unattended Gemini pushes.

## What lane-ops v2 changes (commit 3)
| Area | Change |
|---|---|
| Duplicate fill loops | `fill.sh` takes an atomic `zsystem flock` (the pidfile check raced; 5 loops ran on 10/16) |
| Stale claims | `claim-gate.py --lease-s` heartbeat leases + `renew` / `release --claim`; `lane-lease.sh` renews and releases on every exit incl. `screen -X quit`; `nuc-lane.sh` releases on exit. Killed lanes free their work in 15 min, not 5 h |
| Outsider-triggered runs | `fill-autoqueue.py`, `gemini-feed.py` and `gemini-lane.sh` only take same-repo work by `rupret007` (`LANE_TRUSTED_AUTHORS`) |
| Review->fix loop | `gemini-feed.py` caps gemfix jobs at 3 per PR per 24 h and skips PRs that already have a queued or running job (one writer per branch) |
| Gemini patch failures | `gemini-direct.py --mode edits` (SEARCH/REPLACE blocks) + `apply-edits.py` (exact -> whitespace -> indentation match, unique, atomic); unified diff kept as `GEMINI_EDIT_FORMAT=patch`; tolerant `git apply` ladder for diffs |
| Test loosening | `gat-policy.py` refuses skip/only markers, test-line deletions, CI/runner config and test-script edits before a push; no test command = no push |
| Robustness | autoqueue survives a hung `gh`; claim JSON parsed from the last line; `active_lane_jobs` sees every provider's screens |

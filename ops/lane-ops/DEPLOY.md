# Deploying lane-ops v2 (after Karen PASS)

Order matters: `claim-gate.py` must understand `--lease-s` before any caller sends it.
Each step is reversible: copy the `.bak-lane-ops-v2` file back.

1. Pre-check: `tools/drift-check.sh`. If a live file drifted after this PR's last commit, rebase the
   PR on it first (another job edited the live copy).
2. Mini, claim gate first:
   `cp -p ~/Documents/bob-overnight-inject/bin/claim-gate.py{,.bak-lane-ops-v2}` then copy
   `mini/bin/claim-gate.py` over it. Smoke: `claim-gate.py renew --claim /nonexistent --owner x` -> rc 3.
3. NucBox: copy `gat-policy.py`, `apply-edits.py`, `gemini-apply-test.sh` into `~/nuc-tools/`
   (back up `gemini-apply-test.sh` first). GAT fails closed if `gat-policy.py` is missing, so copy it first.
4. Mini lane scripts (back up each): `lane-lease.sh` (new), `fill-lease.py`, `fill-autoqueue.py`,
   `gemini-feed.py`, `gemini-direct.py`, `gemini-lane.sh`, `nuc-lane.sh`.
   These are read fresh by each new lane, so running lanes are unaffected.
5. `fill.sh` last: copy it, then restart the loop once: `screen -S lane-fill -X quit` and start
   `screen -dmS lane-fill zsh ~/lane-wt/logs/fill.sh`. Running lane screens keep running.
   Check `dispatch.log` for `fill v5 start` and that a second start logs `another loop holds`.
6. Watch one Gemini code job end to end (`q-<job>.gat.1.log` shows `EDITS applied` / `GAT apply opts`).
   To fall back to unified diffs without a redeploy: `export GEMINI_EDIT_FORMAT=patch` in lane-route.conf.

Rollback: restore every `.bak-lane-ops-v2` file and restart the fill loop.

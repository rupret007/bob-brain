# Deploying lane-ops (after Karen PASS)

Each step is reversible: copy the `.bak-lane-ops-v3` (or `-v2`) file back. Run `tools/drift-check.sh` first;
if a live file drifted after this PR's last commit, bring that change into the PR before deploying.

## v3 order (arch-review-2)
1. Mini, claim gate first (callers send `--max-age-min`, `check`, and rely on the B1 release refusal):
   `cp -p ~/Documents/bob-overnight-inject/bin/claim-gate.py{,.bak-lane-ops-v3}`, copy `mini/bin/claim-gate.py`.
   Smoke: `claim-gate.py check --claim /nonexistent --owner x` -> rc 3.
2. NucBox before any Mini lane script: `lane-supervise.sh`, `lane-hooks/` (all four, executable),
   `nuc-test-slot.sh`, `nuc-repo-cache.sh`, `pre-karen-check.py`, then `gat-policy.py`, `apply-edits.py`,
   `codex-win.sh` (smoke: `codex-win.sh --which`), and last `gemini-apply-test.sh`, `gemini-ctx.sh`, `lane-run.sh`.
   Smoke: `lane-supervise.sh run t 30 -- true` -> rc 0; `nuc-repo-cache.sh rupret007/bob-brain /tmp/wt` -> a sha.
3. Mini `~/bin`: `lane-guard.sh` (adds `mini_mem_ok`), `karen-request.sh`, `pre-karen-check.py`.
4. Mini lane scripts (back up each): `fill-queue.py` (new), `lane-lease.sh`, `lane-result.sh`, `lane-route.sh`,
   `nuc-lane.sh`, `gemini-lane.sh`, `gemini-feed.py`, `fill-autoqueue.py`. `lane-route.conf` is already live
   (CODEX_HOST=nuc since 22:50 CT 10/16); only copy it if drift-check shows a difference.
5. `fill.sh` last, then restart the loop once (`screen -S lane-fill -X quit`; `screen -dmS lane-fill zsh ~/lane-wt/logs/fill.sh`).
   Check `dispatch.log` for `fill v5 start`, `fill DEFER` on a refused lease, and `fill-autoqueue WIP` lines.
6. CONDUCTOR-RULES: add "Before any Karen gate request run `~/bin/karen-request.sh OWNER/REPO PR`; send the request only
   on KAREN_REQUEST_OK and paste its report path. Karen keeps the final say."

Rollback: restore every `.bak-lane-ops-v3` file, restart the fill loop. To lift the WIP limit without a redeploy,
add `export FILL_DRAFT_WIP_MAX=N` to lane-route.conf (fill.sh re-reads it every loop and autoqueue inherits it).

## v2 order (kept for reference)
claim-gate first; NucBox `gat-policy.py`, `apply-edits.py`, `gemini-apply-test.sh`; Mini lane scripts; `fill.sh` last.

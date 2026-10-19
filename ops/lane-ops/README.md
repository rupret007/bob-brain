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

## What lane-ops v3 changes (arch-review-2, 10/16)
| Item | Change |
|---|---|
| B1 stale release | `claim-gate.py` picks each owner's newest record by `created` (not mtime) and keys it per (repo, work_id, owner); `release --claim` on a lapsed lease is refused (rc 3) and leaves the file alone, so a late release can't hide another lane's live claim |
| B2 renew failure | `lane-lease.sh` retries a failed renew (`LANE_RENEW_RETRIES`, default 2) then stops the lane (exit 75, release FAILED) instead of carrying on unleased |
| B3 NucBox writer | NucBox lanes run under `nuc-tools/lane-supervise.sh` (own process group, heartbeat file, stop flag). `lane-lease.sh` beats it on every renew and stops it on every exit; a lost ssh or stale heartbeat kills the whole group |
| B4 PR create | `nuc-lane.sh` records `RESULT pr=` only when a PR exists; pre-pr refusal / `gh pr create` failure is a BLOCKER, released FAILED. No Mini fallback |
| B5 queue | `fill-queue.py` is the only writer of `fill.queue` (flock + atomic replace); a refused lease defers the job (`FILL_DEFER_S`, `FILL_DEFER_MAX`) instead of dropping it |
| B6 hooks | every NucBox lane gets `core.hooksPath=nuc-tools/lane-hooks` (via env): pre-push refuses force pushes, branch deletes, a lost lease, and test weakening (`gat-policy.py --push`) for every provider, then runs the repo's own hooks |
| B7 apply-edits | `.git` refused in any case; empty SEARCH only on empty files; writes are mkstemp + fsync + replace, mode kept |
| B8 TTL / waits | `renew` moves `expires` forward by the TTL, capped at `created + max_age_s` (`LANE_MAX_AGE_MIN`, default 360); `check` is a fence; `codex-win.sh` picks the highest settled `--version`; `nuc-lane.sh` claim retry is 3 tries within ~75 s |
| Pre-Karen self-gate | `shared/pre-karen-check.py` (CI collects new tests, mutation smoke on changed lines, body matches head, no weakening, head checks) wrapped by `mini/bin/karen-request.sh`. A lane or the conductor may request a Karen gate only after `KAREN_REQUEST_OK`; Karen keeps the final say |
| Draft WIP limit | `fill-autoqueue.py` queues no new-issue (feature) jobs while more than `FILL_DRAFT_WIP_MAX` (15) trusted drafts wait across the priority repos; fixes to existing PRs keep flowing; an unknown count holds new work |
| Codex host | Codex is NucBox-only (`CODEX_HOST=nuc`; `mini` is refused at launch); no `|| mini` fallback at launch |
| Mini memory | `lane-guard.sh mini_mem_ok` holds new Mini work on memory pressure >= warn, free < 15 %, or swap growth > 512 MB in 10 min |
| NucBox capacity | `nuc-test-slot.sh` caps concurrent test runs at 3; `nuc-repo-cache.sh` keeps one bare clone per repo and hands out worktrees instead of a fresh clone per job |

Known limit: the Windows `codex.exe` uses Windows git, which does not see the WSL hook env; its pushes are still
fenced by the Mini side (`claim-gate.py check`) and by the pre-Karen check.

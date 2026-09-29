# INTEGRATE-FIXED-0256

RESULT: READY

New tip: `a777736b3f0a37c82b0c4c62be8c91117c4c9881`  
Branch: `draft/webbob-integrate-2057`  
Base: `199eb193396802bbbf899292e48cd04a55f9c57e`  
Completed UTC: 2026-09-28T08:17:08.328671+00:00

Regular push to `brain/draft/webbob-integrate-2057` succeeded:
`199eb19..a777736`. The remote tip equals HEAD and the candidate working tree
is clean. This is an offline READY result; no deployment was attempted.

Gemini findings were investigated against the reviewed commit and the running
code layout, with these results:

| Finding | Diagnosis and resolution |
| --- | --- |
| CRITICAL 1: unverifiable `build_info` dependency | The missing-source claim was a review-evidence gap. `webchat/build_info.py` was already tracked at `199eb19` (blob `ec875bbde21864ae093bff8ea9dab7550e1e12ad`), introduced by `096693f`. Its `CODE_ROOT` comes from resolved `__file__`, independent of persistent data and generated manifests. The related `.git.exists()` check was genuinely too weak: invalid Git markers could authorize jobs. It now resolves the Git root and requires the running code's identity module as a committed blob. API report prompts explicitly request `webchat/build_info.py` as evidence. |
| CRITICAL 2: deploy screen contradicts fallback | The claimed contradiction was false. A screen alone never satisfied the planner's project/repository checks. The attempt2 fixture now explicitly verifies the real collector returns only `lane-integrate-deploy-0204`, unverified, with no project, repo, task, job ID or worker, and no queued/claimed source jobs or running workers. Turn 1 still creates Gemini `audit` and MiniMax `test-writing` jobs under parked holds. |
| HIGH 1–2: tests reuse `CODE_ROOT` | Valid evidence concern, with no mispointed root in this worktree. Tests now independently compare the module, test-file location and Git root, and verify the module is committed. Normal repositories and linked worktrees with `.git` files are covered. |
| HIGH 3: relative pins rejected | False defect for this deployment contract. Deployment resolves candidate paths before writing both pins; current production pins are also absolute. Relative paths remain rejected because service working directories can differ. Absolute symlink aliases are accepted and tested. |
| HIGH 4: code nested below Git root | Real layout limitation, though this production candidate is itself a Git worktree root. Committed nested code now resolves its Git root correctly. Pins continue to select the running code directory. Untracked or staged-only nested archives cannot borrow a parent repository's identity. |

The old assignment code failed the new invalid-marker and nested-code
regressions before the fix (`red-checkout-regressions.log`). Both now pass.
`git_checkout_root` is shared by release identity and the assignment fallback;
Git failures, timeouts, inherited Git location overrides, deleted/linked
identity files, rollback copies and incorrect pins are covered. Missing pins
are rejected before any Git subprocess is needed. The pin contract and
screen/fallback distinction are documented in `webchat/README.md`.

| Validation on the new tip | Result |
| --- | --- |
| Full webchat unittest discovery | 342/342 passed |
| Full services unittest discovery | 131/131 passed |
| Bob parity/integration evals | 96/96 passed |
| Quiet-hours and job-results JavaScript tests | Passed |
| app.js syntax, 123 tracked Python files compiled, whitespace | Passed |
| Read-only current-session capture check | All 19 asks passed |

The evals retain all 19 captured asks in order across three conditions: seeded
work, an identified project lane without a worker, and the attempt2 deploy-only
screen with matching pins and parked Barker/Wildflower holds. The services
regression uses `deploy_integrate.submit` through an isolated HTTP adapter,
then real chat, durable queue, scheduler, API-worker, metered transport and
report-saving code. It checks both exact API models, execution timestamps,
report hashes, original receipts, unchanged holds, and inclusion of the tracked
`build_info.py` in both provider payloads. HTTP provider responses, lane health
and semantic acceptance are mocked; these checks do not prove live provider
execution or a live reviewer PASS.

Full suites ran after the commit using isolated BOB_ROOT directories and
canonical temporary paths outside the checkout, with provider credentials
removed. All 362 tracked files match the tested commit. The capture fixture
and all 792 conversation files retain their original bytes. Only the separate
`provider-health.json` runtime cache changed during this window. This repair
did not write any `conductor/webchat/sessions/*.json` file. Barker and Wildflower
remain parked; no empty work-started promises were introduced.

Live deployment pins remain unchanged and still select the rollback whose
manifest is `dff84e37169b30014ff0f48502b8cc66542cf737`.
`webchat/evidence/integrate-tests.json` is refreshed with `sha==HEAD`,
`suite_exit=eval_exit=0`, and `eval.passed=eval.total=96`.

Evidence: `/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-integrate-2057/reviews/integrate-fixed-0256`. The directory contains the red regression,
diagnosis, full suite/eval logs and counts, tracked-source/session hashes,
preservation checks, regular-push output, remote-tip verification and
`validation.json`.

LIVE Gemini + MiniMax MUST be re-run on `a777736b3f0a37c82b0c4c62be8c91117c4c9881` before deploy.
The prior MiniMax PASS and Gemini FAIL on `199eb19` do not cover this new tip.
A later authorized deployment must also pass the real replay/execution rubric.
The review source bundle should include `webchat/build_info.py`,
`webchat/worker_assignment.py`, `webchat/worker_evidence.py`,
`webchat/integration_rubric.py`, `webchat/test_build_info.py`,
`webchat/test_integrate_2057.py`, `services/test_api_workers.py`,
`webchat/deploy_parity.py`, and this report to avoid repeating the omitted-source
ambiguity.

No deployment, live review, service restart, merge, undraft, force-push,
Jeff notification, or Grok/xAI call was performed.

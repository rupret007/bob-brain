# UNBLOCK-1035

Result: **FAIL_OR_ROLLBACK**. Gemini and MiniMax are working; texting's fresh
code review was BOTH_PASS, but the live job-completion gate failed. Rollback is
verified on local and public endpoints at `a777736`. All later deployments are
held. Order authorized by Jeff: texting, gaps, media, Instinct, voice, UI.

Initial authenticated local/public version: `a777736b3f0a37c82b0c4c62be8c91117c4c9881`.
Candidate: `1ca5e12e06c9352ebf38005bcf8e764d03307c3b`, clean worktree, draft PR #21.

Both Gemini (`gemini-2.5-pro`) and MiniMax (`MiniMax-M2.7`) returned HTTP 200 and `VERDICT: PASS` using `conductor/keys.env` in the initial simple-code probe. The existing general parser rejected both valid 13-character verdicts because it requires at least 20 characters. Original evidence: `UNBLOCK-1035-probes-original.json`.

The review-only transport now accepts an exact final `VERDICT: PASS` or `VERDICT: FAIL`, rejects empty/reasoning-only/truncated/ambiguous outputs, and gives each request 600 seconds. Existing lane slots and budget accounting remain in use. Candidate code is unchanged. MiniMax reasoning is separate from final content, as documented in [MiniMax's API reference](https://platform.minimax.io/docs/api-reference/text-chat-openai).

The fixed transport passed both positive and negative controls for each provider:
correct addition returned PASS; subtraction presented as addition returned FAIL.
Evidence: `UNBLOCK-1035-probes-fixed.json`. Four parser regressions plus two
deployment/rollback guard tests passed (`UNBLOCK-1035-harness-tests.txt`). An
initial guard invocation omitted the candidate services import path and failed;
the corrected invocation uses both candidate `webchat` and `services`, as does
the deployment. The initial failure is retained in `UNBLOCK-1035-deploy-guard-tests.txt`.

Fresh texting validation on unchanged `1ca5e12`: 389 webchat/API tests, 139
services tests, zero skipped; parity 100/100; standalone browser proof PASS.
Evidence: `TEXTING-0916-tests.json`, `UNBLOCK-1035-texting-checks.log`.

Fresh review attempt 3: Gemini PASS and MiniMax PASS, gate BOTH_PASS. Neither
request retried or reused an old approval. Evidence: `TEXTING-LIVE-0916.json` and
`TEXTING-LIVE-1ca5e12-0916-attempt3.json` (immutable receipt).

Regular merge and normal push advanced `draft/webbob-clean-0927` from `2b6204a`
to `1fb14316f80226116cd212548f0776178ca84bc7`. Its tree exactly matches reviewed
`1ca5e12`. Draft PR: https://github.com/rupret007/bob-brain/pull/21.
Evidence: `TEXTING-CLEAN-MERGE-0916.json`.

Texting deployment attempt 3 activated with fresh rollback snapshot
`rollbacks/webbob-texting-20260928-104238`. Texting smoke and all 19 frozen live
reply turns passed. The runner launched 13 replay jobs and observed 8 executions;
only 5 jobs succeeded before the failure, so this was **not** a live release pass.
Evidence: `WEBBOB-TEXTING-DEPLOYMENT-0927-attempt3.json`,
`UNBLOCK-1035-texting-deployment.log`.

The failing job was `webchat-f4b8e359666155c6a06900f02b313c8c` (MiniMax, “Review
and regression test-case drafts”). Result acceptance rejected its answer because
it provided architecture findings and investigation commands but no actual
regression test drafts or concrete resolution plan for “Web Bob unblock 1035”.
This was a substantive task-completion failure, not an empty provider response or
verdict parsing failure. No acceptance rule was weakened and no failed result was
treated as success.

The runner revoked the remaining replay claims and restored both service pins to
the fresh snapshot. Local **and** public `/api/version` returned
`a777736b3f0a37c82b0c4c62be8c91117c4c9881`; unrelated screen sessions were unchanged;
no replay jobs remain active or queued. The final task journal has 5 succeeded
jobs and 8 failed/revoked jobs. Independent post-rollback evidence:
`UNBLOCK-1035-after.json`. Deployment finished at 2026-09-28 10:43:32 CT.

| Feature | Source tip | Result this run |
| --- | --- | --- |
| Texting | `1ca5e12` | BOTH_PASS; deployment attempt 3 failed; rollback verified |
| Gaps | `953f440` | HOLD — texting did not pass live |
| Media | `b8aa84a` | HOLD — texting did not pass live |
| Instinct | `c51860c` | HOLD — texting did not pass live |
| Voice | `5ff8b60` (latest fixes, PR #22) | HOLD — texting did not pass live |
| UI | `9be9c58` | HOLD — texting did not pass live |

The five later source branches were not rebased or deployed. Per-feature
`*-DEPLOY-HOLD-1035.md` files record the failed prerequisite and current order.
Each still needs a rebase onto the eventual live tip and fresh full gates.

The allowed clean-branch merge remains `1fb1431`; production was rolled back,
not Git history. The candidate and clean worktrees remain clean. No force-push,
Grok/xAI, real SMS/iMessage delivery, or Jeff notification was used.

Final artifacts: `UNBLOCK-1035.json`, `TEXTING-DEPLOY-1035.md`, updated
`TEXTING-DEPLOY-0916.md`, and `UNBLOCK-1035-release-harness.json`. The prior billing
blocker report is preserved as `TEXTING-DEPLOY-0916-before-1035.md`.

Remaining blocker: make the assigned MiniMax regression-test-writing task produce
the requested concrete test drafts, then obtain fresh release gates and complete
the entire live replay before starting gaps.

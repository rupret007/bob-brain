# TEXTING-FIXED-1605

tip: c6b3e79218674703cd104d16c2a967ba0cb47221
branch: draft/webbob-texting-action-plan-fix-1605
base: 2cd10065b55d4aba4179a1f49e11f1949bbbb5be
draft_pr: https://github.com/rupret007/bob-brain/pull/26

The exact attempt8 f2c47c4c prompt and rejected_result are captured in services/fixtures/texting_action_plan_1605.json with hashes and the exact Missing actionable action plan error. The rejected answer embedded its Action plan heading and Change label inside an escaped Setup input. Deterministic acceptance still rejects it before any semantic vote or publication.

Regression workers now receive an explicit structured report transport in both dispatch and legacy paths, including Gemini, MiniMax, Claude, Codex and Cursor. The worker supplies every case, plan, completion and findings value. api_worker.render_report formats those values into the existing report: separate Target/Setup/Action/Expected lines, the required Action plan or Unblock plan with same-line Change/Validation/Exit condition, one fenced accepted/reason JSON object and Findings/limits. It does not fill missing values or retry tasks. Missing/empty/wrong-type plan fields and malformed/duplicate envelope keys fail closed. Existing valid Markdown reports still pass through unchanged checks. The unchanged check_answer and independent semantic acceptance validate the final report before saving a successful deliverable; formatting alone never establishes completion.

Shared prompts also show literal outer plan labels, distinguish them from labels in test inputs, and require a conditional grounded exit condition. Bounded MiniMax evidence retains complete guards, source-selection tests and required fixtures, with the valid example rendered as plain lines after source evidence. The same 64000-byte source budget and safe tracked-file rules remain. Metadata discloses the rendered fixture fields. report_repository unavailable-worktree=None behavior is unchanged, as are completion JSON parsing, Findings/limits and coding verification.

Reviewer instructions now keep the worker's presentation contract as data and place the current task/answer after historical evidence. They explicitly distinguish historical fixture answer/error fields from the current worker result, and valid nested control reports from the worker's outer report sections. A captured nested-control regression decodes the literal Setup arguments and proves their stated failure/control outcomes while still rejecting a missing outer plan.

Exact-tip validation:
- 389 webchat tests and 176 services tests: zero failures or skips.
- 115/115 parity/replay evals, including six new exact-failure/outer-plan cases.
- Isolated texting browser smoke PASS; no delivery attempt.
- 23 deployment guard tests PASS: ancestry/refetch, durable service identity isolation, lane isolation, failed gates, rollback and claim revocation, exact-task accepted saved-report/hash checks.
- Two fresh real MiniMax probes PASS through dispatch_worker.execute, actual shared lane locks/API/budget, deterministic acceptance and independent semantic review. They replay the exact f2c47c4c prompt and the identical 1035/dd47c4cb task. Both saved answers and SHA-256 values are verified. Queue/report roots alone were isolated; service pins were untouched.

Initial prompt-only tips exposed missing outer fields, invalid reviewer JSON and confusion over historical or nested fixture answers. Their failed jobs remained unpublished and their receipts are retained under TEXTING-1605-initial-* and timestamped probe directories. They do not authorize this tip. Structured formatting adds no fabricated content, acceptance bypass or task retry.

The deployment runner and wrapper are adapted directly from deploy_texting_1508.py. They retain the ancestry fix and durable-svc-peers-1403 policy, require attempt9+, exact-tip offline receipts, fresh Gemini/MiniMax BOTH_PASS, a draft PR and equal-tree regular clean merge. One activation receives a fresh rollback, texting smoke, 19 frozen turns and additional exact 1035/dd47c4cb and f2c47c4c MiniMax jobs. Every result must be accepted and saved with a verified hash. Both additional conversations are included in rollback claim revocation. Any failure restores a777736 and verifies local/public versions.

Evidence: TEXTING-1605-tests.json, TEXTING-1605-*-tests.txt, TEXTING-WORKER-1605.json, TEXTING-1605-runner-checks.json and TEXTING-DEPLOY-1605.preflight.json. Fresh release review and deployment outcomes are recorded separately. No Grok/xAI, force-push, Jeff notification or real SMS/iMessage. Gaps/media/voice/UI/Instinct remain HOLD.

Fresh release reviews: TEXTING-LIVE-1605.md records Gemini gemini-2.5-pro PASS and MiniMax MiniMax-M2.7 PASS on c6b3e79218674703cd104d16c2a967ba0cb47221, attempt9. Context and output hashes are verified. Regular clean merge 667c05cef83d040c3f07d578f1eac2942acff33e retains e1c03ac history and has the identical product tree. bob-brain fetched the merge and verified tip ancestry. Draft PR #26 has the reviewed head. Deployment outcome follows separately in TEXTING-DEPLOY-1605.md.

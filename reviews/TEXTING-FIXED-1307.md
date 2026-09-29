# TEXTING-FIXED-1307

RESULT: VERIFIED-ALREADY-FIXED

tip: eb8029ed9fa17b26becb5487150b3d8981a5a0bb
branch: draft/webbob-texting-jobcomplete-fix-1207
draft_pr: https://github.com/rupret007/bob-brain/pull/24
clean_merge: e6c91a2efbf11d3c922469bcd912e675aea29c14
product_changes: none

The reviewed product fix remains exactly TEXTING-FIXED-1207.md. No new product commit or merge is needed. Existing exact-tip offline receipts were verified by SHA-256: 389 webchat tests, 152 services tests, 104/104 evals, and standalone texting browser proof, all green with no skips. Fresh LIVE Gemini + MiniMax attempt6 BOTH_PASS in TEXTING-LIVE-1207.md and TEXTING-LIVE-1207.json is reused for the unchanged tip; both outputs and the review context match their recorded hashes.

Deploy runner fix: conductor/reviews/deploy_texting_1307.py, adapted from deploy_texting_1207.py. Fetch the clean branch into bob-brain, require its exact recorded SHA, and run both ancestry and tree equality checks there. Never request the clean-merge object from the feature worktree. Exit 128 triggers one fetch/retry and is classified as a repository/object error if persistent; exit 1 remains a genuine ancestry failure. Git fetch uses a regular ref update without force.

Validation: 10/10 isolated runner checks passed. A real shallow feature clone reproduces missing clean-merge object exit 128, while the release repository fetch/check succeeds without adding the object to that clone. Checks also cover transient/persistent exit 128, non-ancestry, clean-ref/tree drift, absent BOTH_PASS, and smoke/completion failures restoring local/public a777736 with replay claims revoked. The first test invocation had a discovery-pattern/import-path setup error; its log is retained as TEXTING-1307-deploy-guard-tests-initial.txt. The corrected invocation passed without a runner code change.

Evidence: TEXTING-1307-runner-checks.json; TEXTING-1307-deploy-guard-tests.txt; TEXTING-DEPLOY-1307.preflight.json.

Preflight: both local and public /api/version are a777736b3f0a37c82b0c4c62be8c91117c4c9881; no active chat reply. bob-brain origin/draft/webbob-clean-0927 is e6c91a2efbf11d3c922469bcd912e675aea29c14, ancestry holds and the trees are identical.

One deployment is authorized through record_texting_deploy_1307.py using the next free deployment receipt slot starting at attempt6 (separate from LIVE review attempt6). All original gates remain: exact-tip receipts, BOTH_PASS, draft PR, fresh rollback, texting smoke, 19 frozen turns, the exact 1035/dd47c4cb MiniMax prompt, accepted saved deliverables, and automatic rollback to a777736 with local/public verification on any failure.

No Grok/xAI, force-push, Jeff notification, or real SMS/iMessage. Gaps/media/voice/UI/Instinct deployments remain HOLD.

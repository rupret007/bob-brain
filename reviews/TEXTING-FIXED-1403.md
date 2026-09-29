# TEXTING-FIXED-1403

RESULT: VERIFIED-ALREADY-FIXED

tip: eb8029ed9fa17b26becb5487150b3d8981a5a0bb
branch: draft/webbob-texting-jobcomplete-fix-1207
draft_pr: https://github.com/rupret007/bob-brain/pull/24
clean_merge: e6c91a2efbf11d3c922469bcd912e675aea29c14
product_changes: none

The texting product remains the reviewed TEXTING-FIXED-1207 tip. Reused exact-tip receipts were verified by SHA-256: 389 webchat tests, 152 services tests, 104/104 evals, and browser proof, all green with no skips. TEXTING-LIVE-1207.md attempt6 Gemini + MiniMax BOTH_PASS is reused; both review outputs and context match their hashes. No product suite or LIVE review was rerun.

The fix is isolated to conductor/reviews/deploy_texting_1403.py, adapted from the 1307 runner, and record_texting_deploy_1403.py. The original deploy_parity.restart still performs the supervisor-locked restart and captures raw before/after snapshots. The runner applies the durable-service identity check to those snapshots for deployment and rollback. Every existing svc-* peer is protected except the restarted svc-webchat/svc-job-runner pair and the known one-shot svc-project-tick/svc-conductor-pass sessions. The latter two are launched by runtime.runner_cycle/schedule_pass. Non-service screens, including lane-* and coding-agent screens, may appear, exit, or change identity. Cancelled job IDs are recorded separately and never exempt a durable screen.

A durable peer changing identity or disappearing still fails the gate. The required reviewer, dashboard-updater, disk-watch, watchdog, and webbob-reviewers peers are protected, as are future svc-* names by default. Evidence records protected identities, ignored snapshots, and any changed durable peers. The original restart result is retained as legacy_other_screens_unchanged for comparison. Other active lane-webbob-* screens block both preflight and activation; this deploying lane is allowed.

The 1307 ancestry fix is retained unchanged: fetch the clean branch in bob-brain, require the recorded merge, check ancestry there, retry Git exit 128 once, and require equal trees. All other deployment, review, completion, acceptance, and rollback gates remain.

Validation: 22/22 isolated guard tests passed. Coverage includes each durable peer changing or disappearing, unknown svc-* peers, optional/non-service churn, restarted-pair changes, the authoritative attempt6 failure snapshots, cancelled IDs not bypassing protection, lane isolation, ancestry/object errors, rejected review gates, and screen/smoke/completion failures restoring local/public a777736 with replay claims revoked.

Preflight: local and public /api/version both report a777736b3f0a37c82b0c4c62be8c91117c4c9881; no active reply and no other lane-webbob-* screen. Draft PR #24 has the exact reviewed head and clean base. bob-brain has e6c91a2, eb8029e is its ancestor, and their trees are equal. All 19 frozen source turns still match.

Evidence: TEXTING-1403-deploy-guard-tests.txt, TEXTING-1403-runner-checks.json, TEXTING-DEPLOY-1403.preflight.json. One redeploy will use the next free slot starting at attempt7 with a fresh rollback and the original texting smoke, 19-turn replay, exact 1035/dd47c4cb MiniMax completion, and accepted saved-deliverable gates. Any failure automatically restores a777736 and verifies local/public versions.

No Grok/xAI, force-push, Jeff notification, or real SMS/iMessage. Gaps/media/voice/UI/Instinct deployments remain HOLD.

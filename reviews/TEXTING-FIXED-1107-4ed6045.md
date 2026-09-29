# TEXTING-FIXED-1107

tip: 4ed6045567c568097721d7f9e94f76da3d991f50
branch: draft/webbob-texting-jobcomplete-fix-1107
base: 1ca5e12 (BOTH_PASS at attempt3, failed substantive live job completion; previous approvals do not authorize release)

The existing worker assignment now requires actual regression drafts as well as a plan. Dispatch and legacy API workers share result_acceptance's deliverable contract: concrete input/setup, action and expected assertions (or actual named test code), plus a short Change/Validation/Exit condition plan for a named unblock. Missing original lane context requires a bounded, conditional plan grounded in supplied code, not a claim of having found the unknown assignment. Deterministic absence checks precede the existing semantic task review; labels or exploratory findings alone cannot substitute for completion. No acceptance retry or new orchestration subsystem was added.

The exact rejected answer from MiniMax job webchat-f4b8e359666155c6a06900f02b313c8c is preserved in services/fixtures/texting_jobcompletion_1035.json. Regression tests cover forced-positive acceptance votes, both API workers refusing publication, missing plans, empty labels, proposed code tests, and peer audit reports. Bounded snapshots prioritize named relevant code and tracked tests so MiniMax can produce grounded drafts within its existing budget.

Prior casual status voice and 0810/0916 fresh coding verification stay intact. No production status/UI renderer changes. The acceptance reviewer still checks substantive task relevance and coding verification; structural presence alone never marks a result successful.

Validation on this exact clean tip:
- Webchat/API: 389 passed, zero skipped, including isolated browser proof.
- Services/API workers: 147 passed, zero skipped.
- Parity/replay evals: 103/103 passed, including all prior 100 checks and three 1035 completion controls.
- Deployment guards: 4/4 passed. Missing reviews cannot activate. Failed smoke and the extra 1035 replay restore a777736 and revoke replay claims.
- Standalone texting browser smoke: PASS; isolated fixtures, no real SMS/iMessage delivery.

Evidence: TEXTING-1107-tests.json records exact SHA, command arrays, counts and log hashes; TEXTING-1107-*-tests.txt and TEXTING-1107-browser-proof hold outputs. Initial run had one fixed parity-count expectation (103 versus prior 100), retained under TEXTING-1107-initial-*. All suites were rerun after correcting the count.

Adapted deploy_texting_1107.py requires fresh BOTH_PASS for this SHA, matching offline hashes, draft PR, and a regular clean-branch merge with an identical tree. It snapshots rollback, retests all three failure fixtures, runs live texting smoke and 19 frozen turns, adds the exact captured 1035 prompt as a real MiniMax job via the existing queue, and requires all jobs to succeed. Actual accepted reports must match saved content and hashes. Any failure cancels all replay claims (including the extra regression conversation), restores a777736 and verifies local/public versions.

Production preflight: a777736 local and public. Review attempt starts at next free slot 4. Deployment is gated on new reviews. PR #21 is already MERGED, so this branch needs a new draft PR.

No Grok/xAI, force-push, Jeff notifications/texts, or gaps/media/Instinct/voice/UI deployment.

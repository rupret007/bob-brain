# TEXTING-FIXED-0916

tip: 1ca5e12e06c9352ebf38005bcf8e764d03307c3b
branch: draft/webbob-texting-diagdump-fix-0916
base: 9cfe548 (failed deployment attempt2; old BOTH_PASS does not authorize release)

The existing dispatch_worker, result_acceptance and mini_worker now require fresh coding verification before success or draft publication. Workers receive explicit instructions to inspect project gates, re-run affected application tests after the final edit, wait for exits and report commands/counts/SHA. Explicit unfinished verification is rejected deterministically; the exact rejected StoryBoard/Cursor answer from job webchat-53ff7beab93c5adaad5c4177ec9b9e7f is captured as a regression.

For Web Bob and StoryBoard, the local CPU runner independently executes release-owned project commands against the clean committed checkout, saves actual redacted output, timestamps, exit statuses and SHA-256 hashes outside the worker checkout, and fails closed on failures/unavailable checks or checkout drift. Web Bob runs the full webchat/API suite, services suite and parity evals. StoryBoard runs its AGENTS.md finish gate: pnpm typecheck, lint, test (including API build/tests), build, and manager:eval. The existing acceptance review now receives the server-observed committed diff, tracked test definitions and validation evidence, and must assess coverage. Other projects keep task/diff-aware acceptance with the same fresh-verification instructions. No new orchestrator or worker lane.

The full services suite tests macOS sandbox-exec itself; the local CPU runner uses Mini's existing isolated BOB_ROOT and credential-stripped environment rather than nesting sandbox-exec. Tests execute repository code. This execution boundary is explicitly included in live review context.

No production status renderer or UI changed. The prior 0810 status-dump fixture remains green with the exact casual answer: “Codex is working on Web Bob. Gemini and MiniMax have work waiting to run. Claude and Cursor are idle.”

Validation on this exact tip:
- Webchat/API: 389 passed, 0 skipped, including isolated browser proof.
- Services/API workers: 139 passed, 0 skipped.
- Parity/replay evals: 100/100 passed, including all 19 frozen turns across three scenarios, status regression, and the captured incomplete-verification answer.
- Deployment guards: 2/2 passed; missing review gate never activates and failed texting smoke restores/verifies a777736.
- Standalone texting browser smoke: PASS; zero real texts, zero mock sends, zero model calls or queued jobs.

Evidence: TEXTING-0916-tests.json (exact SHA, counts, command arrays, log hashes), TEXTING-0916-*-tests.txt, TEXTING-0916-browser-proof/WEBBOB-TEXTING-0927.evidence.json. Initial failed standalone eval import-path run is retained in TEXTING-0916-initial-*; it was fixed and all suites rerun on this tip.

Adapted deploy_texting_0916.py requires fresh BOTH_PASS, offline test/browser hashes, exact draft/clean-tree pins, both failure regressions, all live jobs completed with committed verification evidence, fresh rollback snapshots, and verified local/public restoration on failure. Deployment slot next free is attempt3. Production remains a777736 pending reviews.

No Grok/xAI, force-push, Jeff notifications/texts, or out-of-scope deployment.

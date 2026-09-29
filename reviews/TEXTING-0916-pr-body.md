Coding jobs could report an API fix as passing after running only shared tests and a prepare smoke. This change requires fresh project verification before a result can succeed or publish: explicit incomplete-test claims are rejected, the existing reviewer sees the committed diff and test definitions, and the local CPU runner independently checks the committed Web Bob or StoryBoard result with recorded exits and log hashes.

The casual status voice and texting consent behavior from 9cfe548 are preserved. This extends the existing dispatch, acceptance, and local test runner; no new orchestrator.

Validation at `1ca5e12e06c9352ebf38005bcf8e764d03307c3b`: 389 API/webchat tests, 139 services tests, 100/100 parity/replay evals, 2 deployment guard tests, and isolated texting browser smoke passed, with zero skips or real text sends. Includes the exact rejected StoryBoard answer and prior status-dump regression.

Release is blocked pending fresh BOTH_PASS. Gemini's LIVE review attempt 2 returned HTTP 402 after three transport attempts; MiniMax's LIVE review also exhausted three requests with HTTP 0 / curl exit 28 (timeout). Neither provider returned a code-review verdict; the fail-closed gate is NOT_BOTH_PASS. No deployment or clean-branch merge has occurred. Production remains `a777736`.

Evidence on the Mac: `conductor/reviews/TEXTING-FIXED-0916.md`, `TEXTING-0916-tests.json`, `TEXTING-LIVE-0916.md`, and `TEXTING-DEPLOY-0916.md`. Supersedes merged draft #20 for the new tip. The adapted release runner is `conductor/reviews/deploy_texting_0916.py`; deployment attempt3 remains unused until gates pass.

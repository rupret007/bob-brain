# TEXTING-FIXED-1207

tip: eb8029ed9fa17b26becb5487150b3d8981a5a0bb
branch: draft/webbob-texting-jobcomplete-fix-1207
base: 6670444bd932409b39044c65d651ae4715f2218f (failed LIVE deploy replay; its prior BOTH_PASS does not authorize release)

The exact rejected answer from MiniMax job webchat-dd47c4cb825451b5ab32daa219a11320 is captured in services/fixtures/texting_jobcompletion_1107.json, including answer and worker-prompt hashes. Its 233739-byte prompt supplied only test modules and omitted the implementation. Its empty inline fields, invented symbols and mistaken treatment of unexecuted drafts still fail acceptance. The 1035 and dd47c4cb jobs have identical task text, so a single additional live job replays both incidents.

The existing api_worker now supplies a 64000-byte MiniMax test-writing source snapshot with core completion implementation and fixture evidence even for old prompts naming no files. Named files each receive a bounded share before unrelated material; a compact manifest and explicit truncation notes disclose coverage. Gemini's audit source budget remains 700000 bytes. No private or untracked files become eligible.

Dispatch and legacy API workers share api_worker.report_prompt: the assignment and explicit inline-field contract precede the evidence, with the contract repeated afterward. The contract requests a focused failure/control pair, actual setup/call/assertions, unexecuted labels and a conditional Change/Validation/Exit condition plan for a named unblock. It requires calls to match current code and prevents claiming a proposed test alone resolved the unblock.

The existing semantic result_acceptance reviewer receives the same captured repository evidence as the worker to check symbols and expected behavior. It still rejects incorrect or unsupported tests; deterministic absence/refusal/incomplete-verification checks are unchanged and run first. There is no answer repair, synthetic success, extra task retry or new orchestrator.

Validation on this clean tip:
- Webchat/API: 389 passed, zero skipped; includes browser proof.
- Services/API workers: 152 passed, zero skipped.
- Parity/replay evals: 104/104 passed, preserving all 0810/0916/1035/1107 checks and adding the exact 1107 rejection.
- Deployment guards: 4/4 passed; absent BOTH_PASS cannot activate, failed smoke/completion revokes replay claims and restores a777736.
- Standalone texting browser smoke: PASS in isolated fixtures; no real SMS/iMessage delivery.
- Fresh MiniMax worker probes: 2/2 succeeded on this exact SHA using real dispatch_worker.execute, real API/budget/lane locks and real semantic acceptance. Only the queue/report root was isolated; service pins were untouched. Saved answers and hashes were verified. Both deliver concrete failure/control drafts and conditional unblock plans.

Evidence: TEXTING-1207-tests.json, TEXTING-1207-*-tests.txt, TEXTING-1207-browser-proof, and TEXTING-WORKER-1207.json. Earlier probes and offline results are retained in timestamped worker directories and TEXTING-1207-initial-*; none authorizes this tip. One intermediate semantic rejection drove the same-snapshot review fix; no rejected result was published.

Release: deploy_texting_1207.py requires fresh Gemini/MiniMax BOTH_PASS, exact-tip offline receipts/hashes, a draft PR and an identical regular clean-branch merge. It snapshots a fresh rollback, retests the status-dump and 0810/1035/1107 fixtures, runs texting smoke, all 19 frozen live turns and the exact 1035/dd47c4cb MiniMax job, and requires every job's accepted saved deliverable. Any failure revokes replay claims and verifies local/public rollback to a777736. Offline/probe success is not a live deployment pass.

Local and public preflight remain a777736. No Grok/xAI, force-push, Jeff notifications, real texts, or gaps/media/Instinct/voice/UI deployments. Those lanes remain HOLD.

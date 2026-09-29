# TEXTING-FIXED-0810

tip: 9cfe54840bed5cb0ca7f2e94db7ef6596b014cf7
branch: draft/webbob-texting-onto-a777736
base: ce2482c (the retained clean merge is 1d72c44)

Casual status now summarizes observed work in short sentences. It groups matching worker states, keeps waiting and unconfirmed work distinct from running work, and omits model placeholders, elapsed-time inventories, machine task labels, and job-runner counts. Explicit diagnostics and the complete saved observation remain available.

The existing reply_authority formatter, cooldown mapping, server-owned status route, and status_observation evidence path from integrate a777736/reply-quality branches are retained. No new status subsystem. The release rubric now rejects the additional diagnostic phrases and worker inventories while retaining identity, timestamp, digest, count, execution-source and exact-render checks. Inventory-in-prose assertions were replaced with explicit short-answer/state regressions.

Exact previous failure, session b33fac25-3c8a-452d-8673-47d3a99dd92c turn 3:
> Codex is working on Web Bob. Gemini and MiniMax have work waiting to run. Claude and Cursor are idle.

Validation on this tip:
- Webchat: 389 passed, 0 skipped, including the isolated texting browser proof.
- Services: 131 passed.
- Offline parity/replay evals: 99/99 passed (including all 19 frozen turns across three scenarios and the failed live snapshot).
- Deployment guard tests: 2/2 passed; bad review gate never activates, failed smoke automatically restores and verifies a777736.
- Standalone texting browser proof: PASS, zero real texts or mock sends, no unexpected writes, model calls, or queued jobs. The existing browser wait was changed to a CSP-compatible locator wait; production UI/CSP were not changed.

Evidence: TEXTING-0810-tests.json, TEXTING-0810-*-tests.txt, TEXTING-0810-browser-proof/WEBBOB-TEXTING-0927.evidence.json. Initial old-wording assertion failures and the initial browser harness failure are preserved separately.

No Grok/xAI, force-push, or Jeff notifications/texts. Fresh LIVE Gemini + MiniMax reviews and deployment evidence follow separately.

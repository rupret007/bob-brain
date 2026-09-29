# TEXTING-FIXED-1508

tip: a3d149af9b14d2b99464ce7a2bf647c7eaf89edd
branch: draft/webbob-texting-replay-json-fix-1508
base: eb8029ed9fa17b26becb5487150b3d8981a5a0bb
draft_pr: https://github.com/rupret007/bob-brain/pull/25

Attempt7 failed semantic acceptance after a report omitted an actionable lane plan and completion JSON. The saved task/worker prompt did not explicitly require JSON; only the reviewer's own output schema did. The old reviewer also misdescribed the captured control: its Expected field actually named the fallback repository Path, not a worktree Path. The raw prompt, answer, error and answer hash are preserved in services/fixtures/texting_jobcompletion_1403.json. Its absence of a lane plan still fails, independently of the reviewer's inaccurate details.

Independent-subtask reports and explicit accepted/reason JSON requests now share one worker/acceptance contract. It requires substantive work, an action plan when requested (including non-unblock lane assignments), a Findings/limits sentence for independent subtasks, and one completion JSON object with boolean accepted and a nonempty reason. Missing, malformed, ambiguous, duplicate-key, quoted, wrong-type and negative completion blocks fail before semantic voting or success publication. An accepted=true block is only the worker's statement; the server's independent semantic review still decides completion and checks the same captured evidence. The reviewer prompt distinguishes those two schemas. The JSON parser recognizes actual standalone Markdown fences; escaped fences inside a behavioral test fixture cannot hide the outer completion JSON or later incomplete-verification prose. A real MiniMax probe exposed that false rejection and its focused regression now passes. No answer repair, fabricated success or extra task retry was added.

Dispatch Gemini/MiniMax/Claude/Codex/Cursor and legacy API/tool worker paths receive and enforce the shared contract. The original refusal, verification and exact-text checks remain. Ordinary unrelated replies remain unchanged. Validation functions now precede verbose prompt construction in result_acceptance.py so MiniMax's bounded named-file snapshot contains the full JSON and deliverable checks. A captured-prompt snapshot test proves both guards survive the unchanged 64000-byte budget. Successful-control instructions explicitly require all JSON/plan/findings fixture sections.

report_repository now returns an existing assigned source worktree, raises for a missing source, and returns None for absent/None/non-directory worktrees. The dispatcher stops before evidence or model calls when that source checkout is unavailable, instead of reviewing a possibly unrelated repo. Source-independent project lookup is retained. Focused tests cover all requested cases and prevent unavailable-source publication.

Exact-tip offline validation:
- 389 webchat/API tests, 166 services tests, zero skips or failures.
- 109/109 parity/replay evals; five new 1403 completion cases preserve all prior cases.
- Standalone isolated texting browser smoke PASS; no real delivery requests.
- 22 isolated deploy guards PASS, retaining ancestry/refetch and durable-svc-peers-1403 behavior, rollback, lane isolation and replay-claim revocation.

Worker probes: pending final exact-tip probes. Earlier probe receipts are retained under TEXTING-1508-initial-* and timestamped folders; they do not authorize this tip. The initial full-suite failure was the old eval count (104 versus 109); the later source-evidence layout fix added one services test. Every release receipt must match this final SHA.

The 1508 runner and record wrapper are adapted directly from 1403, with attempt8+ only and a new captured-1403 regression gate. Screen-isolation policy and bob-brain ancestry checks are preserved. Fresh Gemini/MiniMax BOTH_PASS, exact-tip offline receipts, draft PR and an equal-tree regular clean merge precede activation. One release gets a fresh rollback, texting smoke, 19 frozen live turns, the exact 1035/dd47c4cb MiniMax replay, accepted saved deliverables and hash checks. Any failure revokes claims and verifies local/public restoration to a777736.

Evidence: TEXTING-1508-tests.json, TEXTING-1508-*-tests.txt, TEXTING-1508-browser-proof, TEXTING-1508-runner-checks.json, TEXTING-DEPLOY-1508.preflight.json. Local/public preflight was a777736; bob-brain contains e6c91a2; no competing lane-webbob screen was active. No Grok/xAI, force-push, Jeff notifications or real SMS/iMessage. Other deployment lanes stay HOLD.

# Web Bob API workers — ready for draft review

Date: 2026-09-27. Branch: `draft/webbob-apiworkers-2012`, based on
`draft/webbob-replyq-1856` (`15d0ff4`). Requested PR base:
`draft/webbob-clean-0927`. No deployment, service restart, or deployment-pin change.

Jeff's “remember you can use Gemini and MiniMax for the ongoing jobs” now reaches
the server dispatcher. It saves a concrete supporting job for each requested LLM
and replies with the assigned task, worker and durable job ID. Gemini receives a
repository audit and plan; MiniMax receives a review and regression test drafts.
These jobs reference the ongoing source job and can inspect its working checkout.
Identifiable external CLI work can also supply the project/task. Existing coders
keep their claims and edit rights. Saved intents and deterministic IDs survive
restarts without duplicate jobs or result messages.

When there is no identifiable permitted work, a hold, maintenance, a known
missing key, cooldown or exhausted budget, the server explains the limit. A
queued receipt does not claim execution has started. Model-generated
acknowledgements and assignment claims cannot substitute for queue receipts.

Worker execution:

- Gemini job calls use `gemini-2.5-pro` and `GEMINI_API_KEY`; audits, planning and
  research are supported. Research enables `google_search` and preserves returned
  source URLs. Chat and short critiques retain their existing Flash model.
- MiniMax uses `MiniMax-M2.7`, `MINIMAX_API_KEY` and
  `https://api.minimax.io/v1/text/chatcompletion_v2`. It supports repository
  reviews, test-case writing and eval grading.
- Both the chat dispatcher and legacy job runner produce reports. API workers
  have no shell, deployment, patch-application or conflict-resolution tools.
  The server saves accepted Markdown reports and fenced proposed patches under
  `conductor/reviews/api-workers/`. The queue records the report path, result
  hash, acceptance receipt and repository evidence metadata.
- Status and Jobs show each executing API worker's exact model and task using
  server execution metadata and live process evidence.

Credentials load from `conductor/keys.env`. Authentication headers travel through
private curl configuration files, without keys in argv, request URLs or logs.
Known secrets are redacted from stored prompts, results and worker errors.
Repository snapshots exclude credential files, private runtime data, binary
files and links. Directory descriptors and `O_NOFOLLOW` reject concurrent
symlink swaps. The real `webchat/.password` was never printed or used for testing.
Grok/xAI is rejected by the worker allowlist and API transport.

Repository evidence is bounded: 700,000 source bytes for Gemini, 220,000 for
MiniMax, and 48,000 per file. Manifests identify included, omitted and truncated
files. Snapshots use tracked working files and may observe a checkout while its
coder is editing it; they are not transactional or proof of complete coverage.
API output remains a proposal for a tool worker to apply and test.

The existing shared reservations, concurrency limits and 95% budget stop remain
in effect. Pro calls reserve the higher context tier, settle against actual
input/output/thinking usage, and conservatively include the Google Search charge.
Transport/tool configuration was checked against Google's
[GenerateContent reference](https://ai.google.dev/api/generate-content) and
[search documentation](https://ai.google.dev/gemini-api/docs/google-search),
with Pro/grounding accounting from [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).
The MiniMax model and endpoint match the [official M2.7 integration example](https://www.minimax.io/models/text/m27).

Validation on the final implementation:

| Command | Result |
| --- | --- |
| `bash reviews/run-webbob-tests.sh` | PASS: 283 webchat tests + 129 service tests; quiet-hours JavaScript test, app JavaScript syntax, bootstrap compilation and whitespace checks |
| `python3 webchat/bob_parity_eval.py` | PASS: 37/37, score 10.0; CLI now uses an isolated data root and requires every case to pass |
| `python3 bootstrap.py check` | `syntax: PASS` |

New regressions exercise both API workers through real queue claims and report
execution with intercepted provider transport, exact model/endpoint/auth/search
payloads, budget settlement and refusal before HTTP, safe repository reads,
secret redaction, the legacy runner, the original Jeff turn, natural task types,
multiple-project reports, holds, unavailable workers, restart idempotency,
single result delivery, active-coder preservation, and model/task status.
Tests use synthetic credentials and temporary repositories; no paid API call or
live provider-availability smoke test was performed.

Earlier full runs intermittently hit macOS `PermissionError` in the existing
process-group cleanup tests. Focused checks and the final complete suite passed.
The process-cleanup implementation was not changed as part of this work.

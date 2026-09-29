# Texting review triage — 2013

**Result: local checks GREEN; ready for the separate same-tip LIVE rereview.**

**Branch:** `draft/webbob-texting-0927` on `brain`.
**Unchanged local and remote tip:** `78fa870a8ed7178662f97b0394ff80ba32ded63e`.
**Baseline:** `dff84e37169b30014ff0f48502b8cc66542cf737`, verified ancestor.
**Validation date:** 2026-09-27 America/Chicago (2026-09-28 UTC).

No reproducible texting-scope defect was found in the supplied findings. No
runtime, test, or tracked evidence file changed; no commit or push was needed.
These new handoff markers and validation logs remain outside the commit so the
requested review target stays at `78fa870`. The remote ref was checked with
`git ls-remote --exit-code brain refs/heads/draft/webbob-texting-0927`.

## Review inputs and correct scope

Read in full:

- `LIVE-GEMINI-draft_webbob-texting-0927-e1f9ee1-rereview.md`
- `LIVE-MINIMAX-draft_webbob-texting-0927-78fa870.md`
- `LIVE-MINIMAX-brain_draft_webbob-texting-0927-78fa870.md`
- `TEXTING-STILL-FAIL-1841.md` and `TEXTING-FIXED-1841.md`

All source references below refer to the unchanged tip. `git diff --name-only
e1f9ee1..78fa870 -- webchat` is empty: Gemini's implementation target and the
current texting implementation/tests are identical. `git diff --name-only
dff84e3...78fa870 -- services state` is also empty. Both MiniMax reports review
service/state code already in the live baseline. Voice and media are separate
lanes, outside this texting diff.

Review the actual branch with `git diff dff84e3...78fa870 -- webchat` and read
complete files with `git show 78fa870:<path>`. The actual integration is
`Texting`, `BlueBubbles`, and `Andrea`, called from `Chat.submit()` through the
authenticated `/api/messages` route. Searches of the Python/browser sources find
no `TextingConsent`, `Twilio`, `MockTwilioClient`, `_verify_signature`,
`_handle_texting_consent_request`, `_handle_texting_send_request`, `_send_sms`,
`phone_number`, or `hmac_key` implementation to repair.

## Gemini: every finding checked against the code

The G numbers below correspond to its Bugs and Security Vulnerabilities section;
the M numbers correspond to its Missing Tests section.

| Finding | Disposition and actual evidence |
| --- | --- |
| G1: missing constant-time comparison in `_verify_signature` | False API and false comparison claim. `webchat/texting.py:274` uses `hmac.compare_digest` for the actor, confirmation token, and draft fingerprint. There is no webhook signature verifier. |
| G2: duplicate `TextingConsent.get_or_create()` / `.save()` calls | Those APIs do not exist. `webchat/app.py:345` supplies the persistence callback and returns directly after a handled turn. `webchat/texting.py:386` saves ordinary handled turns once. Confirmation intentionally saves consumed consent at line 287 before Andrea, then saves the receipt. Tests at `webchat/test_texting.py:320` and `:335` assert write counts and ordering. |
| G3: `public()` leaks `phone_number` / `hmac_key` | Those fields do not exist. `Chat.public()` at `webchat/app.py:220` excludes all five core-private fields before and after the extension and deep-copies input. `Texting.public()` at `webchat/texting.py:204` removes `_texting` and projects an explicit card allowlist. The authenticated owner must see recipient addresses and the pending confirmation text to review the exact draft; these are intentional card data. The private actor, audit, epoch, and stored fingerprint are not projected into the card. Tests at `webchat/test_texting.py:354` and `:365` cover actual private fields and mutation isolation. |
| G4: send safety relies on a mock / unguarded real Twilio construction | False architecture. The production `Andrea.deliver()` uses authenticated loopback HTTP; it is reached from `Texting.confirm()` only after exact separate-turn, actor, conversation, expiry, revision/body/recipient fingerprint, and token checks, followed by durable consent consumption (`webchat/texting.py:261`). `webchat/app.py:1306` takes the actor from the authenticated session, not request JSON. BlueBubbles has a read allowlist (`webchat/texting.py:95`), and there is no direct BlueBubbles send route in the texting implementation. |
| G5: evidence describes an internal consent object/mock send without a coherent proof | The current report and manifest explicitly describe the blocked bridge. `webchat/texting_proof.py:38` disables sends in its synthetic fixture; lines 55–64 assert a single consumed confirmation, one rejected Andrea probe, no BlueBubbles send, zero deliveries/jobs/model calls, and unchanged live listener identities. `webchat/browser_texting.cjs:50` through the reload assertions show the draft, edit, stale-token rejection, separate submission, and blocked receipt. The manifest's 11 source hashes and five screenshot hashes all match this tip. There is no `test_e2e_texting_flow` or “Texting consent created” assertion in this runner. Mock success is separately covered at `webchat/test_texting_e2e.py:62`. |
| M1: no `compare_digest` test | Already present: `test_token_comparison_timing_safe` at `webchat/test_texting.py:167` spies on the actual primitive for invalid and valid tokens. |
| M2: no public exclusion/API tests | Actual projection tests are at `webchat/test_texting.py:354` and `:365`; HTTP/session tests are at `:456`, and HTTP draft/receipt tests are at `webchat/test_texting_e2e.py:62`. `/texting/consent` and the proposed fields are not this API. The HTTP handler returns `Chat.submit()`'s public projection. |
| M3: no duplicate-save tests | Existing tests at `webchat/test_texting.py:320` and `:335` assert one ordinary write and two ordered confirmation writes; duplicate request replay is tested at `:269`. |
| M4: missing success-message tests | `test_separate_yes_success_message_content` at `webchat/test_texting.py:155` asserts the exact `SENT_VIA_ANDREA` receipt, saved history, sent state, consumed token, and one Andrea request. Draft, edit, blocked, expired, cancelled, and mismatch behavior is covered by the adjacent tests. The proposed consent-created/updated/queued messages do not exist in this synchronous draft/confirmation flow. |
| M5: missing negative send tests | Tests at `webchat/test_texting.py:101`, `:119`, `:183`, `:200`, `:210`, `:245`, and `:254` cover incomplete/embedded approval, replay, wrong actor/chat/token, expiry/restart, cancellation/edit, and tampering. `:279` explicitly asserts no handoff if the pre-send save fails. HTTP E2E at `webchat/test_texting_e2e.py:62` enables the success fixture and still verifies zero sends for the draft and bare “yes,” then exactly one after the separate token. |
| M6: missing signature edge cases | No signature-header endpoint exists. The real token/fingerprint rejection tests are at `webchat/test_texting.py:167`, `:200`, and `:254`; HTTP auth, missing CSRF, session binding, and expired-session checks are at `:456`. |
| M7: missing consent state transitions | Actual states are pending/editing/expired/superseded/cancelled/delivery_unconfirmed/confirmed_not_sent/sent. Tests at `webchat/test_texting.py:143`, `:183`, `:210`, `:225`, `:245`, and `:290` check success, blocking, expiry, replacement/cancellation, and durable uncertain delivery after a failed receipt save. `owner_confirmed_send` and `sent_at` are not fields in this implementation. |

Gemini's remaining observations also reference nonexistent tests/fixtures:
`test_texting_consent_endpoint` and `MockTwilioClient` are absent.
`browser_texting.cjs` is the isolated Playwright proof, not the shipped client;
the shipped card UI is in `webchat/static/app.js`. Thread text and card content
are rendered with `textContent`; the browser confirmation button only fills the
composer. The actual fixture is `MockMessaging`.

## MiniMax at `draft_webbob-texting-0927-78fa870`

| Finding | Disposition and actual evidence |
| --- | --- |
| BUG-1: shell injection through `gh --repo` | False for the cited path. `services/draft_publish.py:20` validates the remote before calling the helper; the branch is built from a validated task ID at lines 22–24. `:58` passes an argv list to `command.run`; `services/command.py:35` uses `Popen` with no shell requested. The supplied semicolon example is neither shell-evaluated nor accepted by the publication path. Baseline code, unchanged here. |
| BUG-2: unresolved/unvalidated `cwd` | `services/dispatch_worker.py:30` already resolves the configured repository; `prepare_task()` returns the assigned task checkout and checks branch ownership (`:40`). Malicious operator configuration is a broader trust-boundary concern, not a demonstrated texting input path. No texting-scope exploit was supplied. |
| BUG-3: symlink attacks in task-run writes | `services/state.py:31` writes a fresh temporary file and atomically replaces the destination, rather than following a final-file symlink. Parent-directory symlink hardening is a possible baseline improvement under a hostile local-writer threat model; this review supplies no texting-controlled path to those directories. No claim that all parent-directory races are eliminated. Outside this diff. |
| BUG-4: three `gh` calls / no idempotency | The code does list → create-if-absent → list to verify the resulting draft and SHA; the final `if` does not launch another process. The proposed replacement still makes the same three calls when creating a PR. `services/dispatch_worker.py:80` locks execution per task. No concrete texting regression is shown. |
| BUG-5: project test does not simulate acceptance retries | This conflates two tests. The project fixture tests persisted workspaces; retry behavior is tested independently at `services/test_result_acceptance.py:11`. In `services/test_dispatch.py:377`, `review` is a loop value (string or exception), not a Mock. The actual mock invocation count at `:386` is checked. |
| T-1: missing standalone project-catalog merge test | A focused shipped-fallback/duplicate-key unit test would be additional baseline coverage. Local mappings are exercised by the four-project integration test at `services/test_dispatch.py:65`. No changed texting behavior depends on a catalog merge. |
| T-2: missing unavailable-`gh` test | A dedicated unavailable-binary test is absent; this is baseline resilience coverage, outside texting. The described empty-stderr RuntimeError is inaccurate for process creation failure: `FileNotFoundError` escapes the helper before a result exists and is handled by the dispatch failure path. |
| T-3: no retry-exhaustion coverage | `services/test_result_acceptance.py:68` supplies constant malformed responses, so the second parse fails too and `ResultRejected` is required. The loop at `services/result_acceptance.py:59` explicitly rejects the second decode failure. An additional exact call-count assertion is optional coverage, not an uncovered texting failure. |
| T-4: fields checked only in memory | False premise: `services/test_dispatch.py:82` calls `queue.tasks(self.root)`, which reads the journal under lock (`state/task_queue.py:134`). `transition(..., **fields)` at `:232` appends the updated fields at `:264`. The integration test verifies persisted worktree/branch/repo/project; a dedicated `prompt_file` assertion would be extra baseline coverage. |
| Goal gaps: voice barge-in / iPhone media absent | Different lanes. Neither is required to validate this texting diff. The report itself says the texting lane is otherwise solid. Existing offline parity evidence must not be read as live proof of voice/media or real outbound delivery. |

## MiniMax at `brain_draft_webbob-texting-0927-78fa870`

| Finding | Disposition and actual evidence |
| --- | --- |
| 1: unsupported transition kwargs / wrong `atomic_write` arguments | False. `state/task_queue.py:232` explicitly accepts `**fields`, persists them at `:264`, and is exercised by the disk-reading project test. `services/state.py:31` accepts exactly the two arguments supplied. |
| 2: redaction may miss secrets | An unspecified baseline hardening concern, not a reproduced leak. `services/dispatch_worker.py:61` removes loaded credential values and several key formats. This does not claim universal secret detection. Actual texting transport-error scrubbing is tested at `webchat/test_texting.py:405` and `:417`, and private texting exchanges are withheld from providers at `webchat/texting.py:221`. |
| 3: exact draft SHA validation too strict / index access unsafe | Intentional safety invariant. `services/draft_publish.py:73` rejects a PR at an unverified SHA; Python short-circuiting checks length before indexing. Git garbage collection does not rewrite commit IDs. This task explicitly forbids force-pushes and undrafting, so relaxing the check would violate the required workflow. |
| 4: project membership accepts empty strings / rejects valid lists / names may differ | False. `state/task_queue.py:172` rejects an empty string or a list/tuple as a project value; the API expects one allowed project name. `None` means publication not requested. `services/projects.json:5` contains the exact `Fantasy Football` key. |
| 5: whitespace reasons accepted | False: `services/result_acceptance.py:75` rejects a stripped-empty reason. A minimum length of three is a new policy preference, not an existing requirement or a texting defect. |
| 6: `gh` command injection | Same rebuttal as BUG-1 above: validated publication inputs and argv execution without a shell. |
| 7: local project overrides are a vulnerability | `services/dispatch_worker.py:35` explicitly documents retaining local overrides. This is operator configuration already in the baseline, with no demonstrated texting-controlled modification path. Broader configuration trust policy is outside this lane. |
| 8: project name injects PR body content | `state/task_queue.py:172` allows only fixed project names; IDs are generated from UUIDs at `:180` and validated before publication. The proposed newline-bearing project name is not accepted by the queue. Baseline code. |
| 9: no project-catalog merge unit test | Same T-1 disposition above: possible focused baseline coverage, not a texting blocker. |
| 10: integration test expects unsupported kwargs | False: `transition` accepts and persists the fields; the integration test passes in the full 121-test service run. |
| 11: no dedicated `draft_pr`-without-project test | Dedicated coverage is absent. The guard exists at `state/task_queue.py:174`; adding a baseline queue test is outside this texting change. No bypass was demonstrated. |
| 12: no SHA-mismatch/multiple-PR tests | Dedicated cases are absent from the draft-PR test. The actual condition at `services/draft_publish.py:73` fails closed for both. Additional baseline coverage is reasonable separately; removing SHA verification is not. |
| 13: inconsistent `str()` wrapping | False: both `worktree=str(cwd) if cwd else None` and `repo=str(repo) if repo else None` already use the same conversion/guard (`services/dispatch_worker.py:154`). |
| 14: `review` is a Mock rather than a string | False: it is the value from the tuple in `services/test_dispatch.py:377`. `ask` is the Mock. The comparison at line 386 is valid and passes. |

## Fresh checks on the unchanged tip

All required commands ran from the requested worktree root. The webchat process
used the already-installed browser with
`PLAYWRIGHT_BROWSERS_PATH="$PWD/webchat/node_modules/.cache/ms-playwright"`.

| Command | Actual result | Log |
| --- | --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **292 passed, 0 skipped**, 53.631 s; includes isolated blocked-path browser proof and HTTP mock success | `TEXTING-2013-webchat-tests.txt` |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **121 passed, 0 skipped**, 7.218 s | `TEXTING-2013-services-tests.txt` |
| `node --check webchat/static/app.js` | **PASS**, exit 0 | `TEXTING-2013-js-check.txt` |
| `git diff --check` | **PASS** | No tracked changes |

The service log's restart/provider messages describe mocked fixtures, not live
operations. The webchat suite's temporary non-repository fixtures produce Git
diagnostics; the completed suite reports `OK`, with no failures or skips.

Rechecked the saved browser manifest: **11/11 source hashes**, **5/5 screenshot
hashes**, matching screenshot names, blocked audit/receipt, one rejected Andrea
probe, and zero recorded deliveries all agree. The fresh browser test ran in its
own scratch output directory; it did not overwrite the committed 0927 artifacts.

`WEBBOB-EVALS-0927.md` and `.json` are present in HEAD and byte-identical in both
review directories. Their **4/4 source hashes** match this tip. They preserve
the original **24/24 offline checks plus 3/3 strict status checks** and the
original execution timestamp. No eval was rerun or relabeled as live.

## Handoff

`TEXTING-READY-2013.md` records local green/review readiness for this exact SHA.
No remaining real texting blocker was identified. No 2013 STILL-FAIL marker is
needed. The historical 1841 STILL-FAIL marker is retained: its pending external
LIVE review/eval decisions are not being represented as passes here.

The separate screen still owns fresh LIVE Gemini and MiniMax verdicts on
`78fa870a8ed7178662f97b0394ff80ba32ded63e`; the conductor owns acceptance of the
explicitly limited offline eval evidence. Production Andrea delivery remains a
separate approved-bridge dependency. READY here authorizes neither deployment nor
real sending, and does not claim completed external gate approval.

Markers and fresh logs are copied to both this worktree's `reviews/` and
`../../conductor/reviews/`. No deploy, service restart, branch/PR merge, undraft,
force-push, real outbound message, Jeff notification, password disclosure, or
`~/STOP-WEBBOB` creation was performed.

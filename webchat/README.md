# Bob web chat

Open **http://127.0.0.1:8787** on the mini. The login password is in
`conductor/webchat/.password` (owner-only, mode 600). To see it locally:

```bash
cat ~/Documents/bob-overnight-inject/conductor/webchat/.password
```

The app uses Python's standard library. No packages, API account changes, or
Claude subscription are needed. The messenger supports mobile layouts, dark mode,
saved conversation selection, new conversations, polling replies, and Stop.
Enter sends on a desktop; Shift+Enter adds a line. On a phone, use Send.

The five tabs are Chat, Jobs, Songs, Models and Settings. Jobs shows current
workers and saved results; View jobs in Chat opens it without sending a message.
Models shows current activity and reply availability, with measured usage in
collapsed details. Songs puts lyrics and Save first, with chords, audio and saved
versions below. Settings saves your preferred first-choice model on this device.
Opening these tabs does not request a model answer or change the queue.

## Conversation and provider behavior

Short messages use a fast path (**Gemini → MiniMax → Cursor → Codex**, a 60s initial budget,
then any untried providers), per the later `WEBCHAT-READY.md` phone brief.
Longer/coding/debug work tries **Codex → Cursor → Gemini → MiniMax**. Claude is never in the
automatic route. Codex uses the existing ChatGPT login with API-key environment variables
removed and `forced_login_method="chatgpt"`. No credentials are changed. Native
`codex exec resume <exact-thread-id>` preserves continuity; it never uses `--last`
and therefore never picks up an unrelated coding job. Unsupported/unavailable
saved sessions use recent conversation context. See the official
[Codex non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

Cursor uses `cursor-agent --trust --mode ask --print --output-format json`.
Gemini and MiniMax use `webchat/api_call.py`, which calls the same metered
`services/api.py`/`budget.py` transport as the ask scripts, sharing three bounded
API slots per provider. MiniMax has a **$59 chat ceiling** even if background credit
is increased elsewhere; the child process applies the lower of the chat and shared caps.
Reservations and uncertain calls count toward the cap. Lane health shows that
committed amount, not just settled charges.
Both API lanes default to a $48 shared ceiling, warn at 70%, reduce concurrency
to one at 85%, and reject reservations that would cross 95%. Configure lower
ceilings with `BOB_GEMINI_CAP_USD` and `BOB_MINIMAX_CAP_USD`. CLI plan percentages
are unknown unless observed quota data is supplied in the private
`conductor/plan-usage.json`, for example `{"codex":{"used_percent":86,"reset_at":1790535600}}`.
Observed 95% usage stops that CLI until its reset; provider rate-limit responses
also impose cooldowns. Token counts and estimated dollars do not stand in for
subscription quota measurements.

## Max-mode tasks

Ordinary work requests such as `Ok figure out what is wrong with Gemini` and
`fix the login button` go directly to the durable dispatcher. A server receipt names
the job only after the queue write succeeds; claim updates name the actual worker,
and the completed result is posted in the originating conversation. Model prose
cannot acknowledge queue or inbox effects. Explicit small text writes such as
`write hello to /tmp/example.txt` use Codex, Cursor or Claude with file
tools; success requires the server to verify the changed file and its contents.

Named multi-project requests create one durable job per project. For example,
`prioritize Web Bob, WebJam, AdoptIQ, StoryBoard` saves the order; `push everything
to the max and fix anything you find` queues four project jobs. Each receipt sentence
names the project and requested worker; job IDs stay in structured job data. Assignment prefers ready
compatible lanes and accounts for existing claims and queued work. Coding jobs
use Codex/Cursor; Gemini and MiniMax produce repository reports and proposed patches.

“Remember you can use Gemini and MiniMax for the ongoing jobs” now assigns real
jobs: Gemini gets a whole-repository audit and plan, and MiniMax gets a review
with regression test drafts. The server names each task, worker and durable job
ID after saving it. Existing coding claims continue unchanged. Missing work,
holds, maintenance or unavailable lanes get an honest explanation, never a
readiness-only acknowledgement. A queued receipt means waiting for runner
capacity; a started receipt requires a recorded worker claim.

When no permitted ongoing job or identified project lane remains, matching
webchat and dispatcher deployment pins can identify the running Web Bob Git
checkout for these API reports. The assignments explicitly say no current task
or execution is confirmed. This fallback only supplies Web Bob repository
context to API workers; project/global holds, maintenance and provider
availability still apply. Missing or mismatched pins cannot supply context.
`webchat/build_info.py` is a tracked source module: `CODE_ROOT` comes from its
resolved `__file__`, never a generated manifest or the persistent `BOB_ROOT`.
Git must resolve a real checkout and find that module in HEAD. Normal checkouts,
linked worktrees (`.git` files), and tracked nested code directories are supported;
an untracked rollback/archive under another repository cannot borrow its identity.
The pins at `conductor/state/webchat-code-root` and `dispatch-code-root` must
both contain absolute paths resolving to that running code directory (including
the code subdirectory in a nested layout). Deployment writes absolute paths with
a trailing newline; absolute symlink aliases are accepted, relative paths are
rejected because the services can start from different working directories.
An unverified `lane-integrate-deploy-0204` screen with no project, repository or
task does not supply project context or block this fallback. The attempt2
regressions assert those observed fields before checking real Gemini `audit`
and MiniMax `test-writing` jobs, while preserving Barker and Wildflower holds.

Named API requests also support audits, planning, research, repository reviews,
test-case writing and eval grading. Gemini job calls use `gemini-2.5-pro`;
research enables `google_search`. MiniMax uses `MiniMax-M2.7`. The runner supplies
bounded tracked repository evidence, omitting credentials, links and private
runtime files. Accepted reports and fenced proposed patches are saved under
`conductor/reviews/api-workers/`; API workers never deploy, apply changes or
resolve conflicts. Status and Jobs show the task and exact executing model.

Conversation files also save explicit holds and the latest permission transition.
`hold off on Web Bob` blocks new submissions for that project; `go`, `resume`, or
`the hold is lifted` clears the applicable hold. An explicit project push also
authorizes those projects. A held request survives a reload and can be resumed.
Holds govern new chat submissions; they do not stop already queued/running jobs
or restart services. Old conversations migrate user directives in order without
dispatching them, and assistant text cannot restore a cleared hold.

Status questions, including `is it moving along now?`, get a short server summary
of live work: task label, worker/model and elapsed process time. Read-only `screen
-ls` and `ps` observations include `lane-*` work and standalone CLI workers outside
the queue. Queue claims, screen descendants and CLI wrappers are joined to avoid
duplicates; live workers override cached ready lanes. Desktop apps and helpers
are excluded. Open screens without a confirmed worker and unavailable checks are
reported as unverified. A running process proves activity, not forward progress;
an exact model variant is shown only when present in the process arguments.
Task labels come from queue titles/projects or readable screen names, never raw
process prompts. Missing task details use a readable project or lane label; missing exact model metadata stays unreported. Internal job IDs, screen
names, PIDs and finished-job history are shown only when requested. Ordinary chat
never recommends special job syntax.

Operational replies also use lane locks and generation health from
`webchat/sessions/provider-health.json` plus `logs/webchat-failover.log`. The server
identifies the actual answering provider on each attempt. Old chat errors never
override recovered health, and configuration probes alone do not prove generation.

Say `Max mode: review ...` or `Go to the max: implement ...`. Web Bob saves a
restart-safe plan and queues independent packages for Codex (implementation),
Cursor (integration/tests), Claude (design critique), Gemini (alternatives and
capacity), MiniMax (failures/recovery), and mini (local tests). The default split
uses these standing roles; provide task-specific packages when boundaries matter:

```text
Max mode: review this design and supplied evidence ...
[codex] Inspect queue invariants and cite code.
[cursor] Inspect the delivery path and test coverage.
[claude] Critique assumptions using the supplied evidence.
[gemini] Calculate throughput under the stated durations.
[minimax] Analyze crash recovery using the supplied evidence.
[mini] Run services/test_services.py.
```

API report packages receive a server-collected repository snapshot. Claude and
answer-only analysis packages still need evidence in the request.
Coding packages own separate production/test files on private draft branches.
Local commits are reported for review; max mode does not integrate or publish
them. Mini accepts existing `services/test_*.py` or `webchat/test_*.py` suites,
uses an isolated data root, strips credential environment variables, and has a
five-minute execution limit.

The runner refills available slots every five seconds, routes analysis to Claude
and API workers before tool workers, and shifts failed or capped work to a
compatible provider with headroom. Busy pinned lanes retain their queued work.
After every package finishes or exhausts retries, a local reducer posts one
combined answer with attributed results and failures. It preserves disagreements
and does not spend another provider call to deliver the results. Saved answers
and deterministic group IDs prevent duplicate delivery across restarts.

Explicit chat provider choices try that provider first, then the normal fallback
chain. Claude remains explicit-only in ordinary chat and participates in max mode.
`/api/jobs` exposes group membership, attempts, PIDs and execution timestamps.
Run `python3 webchat/live_maxmode_proof.py run --root <live-data-root>` for the
authenticated five-provider overlap proof; `resume` and `verify` reuse its private
receipt without submitting another request.
Fallbacks receive up to the last 20 messages (24,000 characters) plus bounded, redacted handoff, brain,
status, review and queue snapshots. The provider and fallback reasons appear
beside the reply. An exhausted provider chain produces an honest queued message.
The saved turn automatically retries when a cooldown expires; Stop cancels it.

Codex runs read-only with no approval prompts or inherited user-config MCP tools;
Cursor runs in ask mode for chat. Providers answer from supplied context. The
separate server dispatch handler queues work; model replies cannot invoke it.
Every provider receives the current
handoff and the hard rules: drafts only, no merges/undrafts/force-push, no outward
messages without Jeff's yes to the exact text, no spending/login changes, no
touching Andrea or other workers' edits, and one WebJam coder. Older brain memory
cannot override those rules.

`sessions/<uuid>.json` stores each conversation and its Codex thread ID, mode 600
inside a mode-700 directory. Conversation history survives server restarts.
Login cookies expire after 12 hours and are invalidated by logout or a restart.
An interrupted running reply is marked as interrupted; it is never automatically
replayed. A waiting all-down request survives restart with its original user turn
and refreshed operational context.
Only one reply runs **per conversation** — not globally across all chats (other conversations can reply in parallel). CLI
calls use `chat-<provider>` locks separate from background `lane-*` locks; a busy
CLI slot falls through to the next provider. Handback: `conductor/handback/`
(BOB-STATE in, HANDBACK-LOG out). Natural requests such as `fix the login button`,
`review PR #161`, and `have Claude review this design` queue durable tasks without
a second confirmation. `go` accepts the most recent clear work proposal; an
ambiguous request gets one short question. Ordinary answers have no job footer.
Receipts say, for example, `I queued “Review PR #161” for Claude.` only after
the durable write. They remain unchanged at their original timestamps.
Structured job data records actual claims and execution; a separate completion
message names the actual worker and links verified project results.
The job runner launches work as capacity becomes available; nothing merges
automatically. Retransmitting the same request ID does
not duplicate work. The server saves intent before queue writes and acknowledges
the job only after the fsynced journal append. Interrupted writes are reconciled
idempotently. Queue updates share a lock and fence stale claim tokens.

Stop and per-provider deadlines terminate the process group and captured nested
groups belonging to this chat. Stdin is an EOF-terminated prompt file or
`/dev/null`. Defaults: Codex/Cursor 180s; Gemini/MiniMax/explicit Claude 120s.
Override a lane with `BOB_WEBCHAT_TIMEOUT_CODEX` (or `_CURSOR`, `_GEMINI`,
`_MINIMAX`, `_CLAUDE`), 15–600s. `BOB_WEBCHAT_TIMEOUT` supplies the CLI default.

Failures are classified as sign-in, usage limit, timeout, nonzero exit, invalid
output or network. Breakers cool for 5, 10, 20, then 30 minutes; a parseable usage
reset overrides that duration. One half-open attempt tests recovery. Success
closes the breaker; a login probe does not clear a quota failure. Checks at startup
and every 10 minutes verify CLI login or API configuration/TLS reachability,
without generation spend. The lanes panel distinguishes probe results from a
completed answer. Breakers persist in private `sessions/provider-health.json`.

Every routing attempt, skip, failure, switch, cancellation, probe and queued retry
is logged as JSON lines in `logs/webchat-failover.log` (mode 600). It contains
IDs, canned reasons and timestamps, not prompts, model output or credentials.

## Start and login after reboot

```bash
bash ~/Documents/bob-overnight-inject/conductor/webchat/start.sh
```

This idempotently starts the `svc-webchat` screen. Repeating it checks the login
page and the protected API. Logs are in `logs/webchat-server.log` and
`logs/webchat-launchd.log`. HTTP requests and model transcripts are not logged.

```bash
bash ~/Documents/bob-overnight-inject/conductor/launchd/install.sh --webchat-only
```

This installs and loads `com.jeff.bob-webchat` without touching the other services.
The regular `install.sh` installs all three LaunchAgents. The webchat agent checks
once a minute and starts a missing screen. LaunchAgents run at **user login**,
not before login. A live but unresponsive screen is reported, never killed.

**macOS permission:** if `webchat-launchd.log` says `Operation not permitted`, open
System Settings → Privacy & Security → Full Disk Access, add `/bin/bash` using
Cmd+Shift+G in the file chooser, and enable it. Then rerun the install command.
The machine's initial verification hit this permission gate; the live screen was
started successfully from the authorized terminal. Merely loading the plist does
not establish that automatic startup works. Check it after granting access:

```bash
launchctl kickstart gui/$(id -u)/com.jeff.bob-webchat
launchctl print gui/$(id -u)/com.jeff.bob-webchat
curl --noproxy '*' -i http://127.0.0.1:8787/login
```

For a deliberate chat restart, stop only the `svc-webchat` **server** screen you
started (`screen -S svc-webchat -X quit`), then run `webchat/start.sh`. This signs
out browsers and interrupts an active reply. Other workers are unrelated.

## Phone, MacBook and off-home access: Tailscale Serve

Authenticated `POST /api/messages` accepts `provider: "auto"` (default), or an
explicit `minimax`, `gemini`, `codex`, `claude`, or `cursor`. Explicit selection
tries that provider first, including status questions, then falls back with visible
attempts if it fails. The separate `worker` field routes durable background tasks.
`live_integration_proof.py run --root <mini-root>` verifies all five providers
through chat; `verify` rechecks their saved answers without new model calls.

The app always binds **127.0.0.1:8787**. A LAN IP URL will not work. Use Tailscale
Serve's private HTTPS proxy with your devices on the same tailnet. Do not open
router ports or use Tailscale Funnel. See the official
[Tailscale Serve instructions](https://tailscale.com/docs/reference/tailscale-cli/serve).

1. Connect Tailscale on the mini and on your phone/MacBook. During initial
   verification the mini's Tailscale was **Stopped**, so remote access was not
   enabled or claimed to work.
2. Allow the mini's exact HTTPS origin, then restart webchat as described above:

   ```bash
   printf '%s\n' 'https://jeffs-mac-mini.tail758ab4.ts.net' > ~/Documents/bob-overnight-inject/conductor/webchat/.public-origin
   chmod 600 ~/Documents/bob-overnight-inject/conductor/webchat/.public-origin
   ```

   If Tailscale assigns a different name, use that exact `https://…ts.net` origin.
   The allowlist rejects other Host headers and origins; forwarded headers cannot
   expand it. Local access continues to work.
3. Inspect existing mappings with `tailscale serve status`. If HTTPS port 443 is
   available, enable the private proxy:

   ```bash
   tailscale serve --bg http://127.0.0.1:8787
   tailscale serve status
   ```

4. Open **https://jeffs-mac-mini.tail758ab4.ts.net** on the connected device and
   use the same Bob password. HTTPS cookies add `Secure`; all cookies are HttpOnly
   and SameSite=Strict. Disable just this mapping with `tailscale serve --https=443 off`.

The password, optional origin, session files, and browser evidence are gitignored.
No directory browsing or arbitrary shell/file HTTP endpoint exists. All API
routes require login; mutations also require an unpredictable CSRF token.
Login attempts and request sizes are bounded. Model output is displayed as text,
so embedded HTML cannot execute. Known secrets are redacted from snapshots,
reports and replies; messages containing detected secrets are rejected before
being stored or forwarded. Avoid pasting credentials into chat.

## Verification

### Text threads and reply drafts

The **Texts** chip lists recent threads. Chat supports `read texts from Alex`,
`summarize texts from Alex`, and `draft reply to Alex: I’ll bring the charts at 6.`
Use a full name, address, or exact thread ID when several threads match. Web Bob
does not guess between matching recipients or SMS/iMessage duplicates. Summaries
are local, extractive snapshots of at most 30 messages with counts, dates, and
recent excerpts. Draft cards preserve the supplied body and display all recipient
addresses plus the thread ID. Thread content and draft history stay out of model
requests and the shared handback ledger.

Send the displayed `yes wbtxt-…` as a **separate chat message** to record consent
to that exact card. Merely filling the composer does not confirm anything. Tokens
expire after five minutes and are bound to the conversation, login, recipient,
body and revision. Editing clears the token before the editor opens; reviewing
the edit creates a new card/token. Cancellation, another turn or draft, logout,
and server restart invalidate consent. An unrelated conversation’s work controls
keep their normal behavior. Consent and its exact recipient/body audit are saved
in the private conversation file (mode 600), with duplicate requests handled once.

**Production delivery remains blocked by the installed Andrea bridge.** The installed Andrea
control API rejects both direct sends and message-action `send`/`send_again`.
A valid Web Bob yes produces **“Not sent”**, consumes the token, and records only
local consent when the bridge is unavailable. With credentials configured, a
valid confirmation probes Andrea’s `/web-bob/send` once; the unavailable bridge
returns an honest blocked receipt. No direct BlueBubbles send, delivery queue or
automatic retry is used. Andrea currently
requires a fresh approval on its own registered Telegram chat or Messages
self-thread; Web Bob cannot impersonate that owner message. An independently
approved Andrea bridge is still required to finish outbound texting parity.

BlueBubbles reads use its existing
`~/Library/Application Support/bluebubbles-server/config.db`, opened read-only
for `socket_port` and `password`; `chat.db` and Andrea’s filesystem are not used
by Web Bob. A test/development instance can set `BOB_BLUEBUBBLES_CONFIG_DB` to a
separate config database. Only `POST /api/v1/chat/query` (a read query) and
`GET /api/v1/chat/<guid>/message` are allowed. Requests use loopback, disable
proxies/redirects, have a five-second timeout, and bound response size.

Optional `texting status` uses authenticated `GET /health` at
`BOB_ANDREA_CONTROL_URL` (default `http://127.0.0.1:4315`) with
`BOB_ANDREA_CONTROL_TOKEN` provisioned by the operator. The URL must be literal
`127.0.0.1`; neither credentials nor URLs can be set from chat. Only a separate,
exact confirmation permits the Andrea bridge probe. Consent is durably consumed
before handoff; if recording the result fails, the saved draft says delivery is
unconfirmed and the token cannot be reused, including after restart. No environment or running service
configuration is changed by this feature or its verification scripts.

Run `python3 webchat/texting_proof.py` from this checkout for an isolated browser
proof of the **blocked “Not sent” path**, with mock BlueBubbles and synthetic
contacts only. Set `BOB_PLAYWRIGHT_MODULE`
and `BOB_CHROMIUM_PATH` to an existing Playwright/Chromium installation as needed.
It creates a private data root inside `reviews/`, binds two spare loopback ports,
uses the actual login/chat UI, writes screenshots plus JSON evidence to `reviews/`,
and closes only its own fixtures. It never uses the live services or models.
The JSON evidence and five screenshots describe this same blocked path: one
rejected mock Andrea probe, zero mock deliveries and zero real sends. Mock success
(“Sent via Andrea”) is covered separately by the HTTP E2E and Python unit tests.
Use `--output-dir <directory>` for scratch evidence; the optional browser unittest
uses its temporary directory so routine tests do not rewrite committed artifacts.

### General checks

```bash
python3 conductor/webchat/test_webchat.py
python3 -m unittest discover -s conductor/webchat -p 'test_*.py' -v
python3 -m py_compile conductor/webchat/app.py conductor/webchat/providers.py conductor/webchat/start.py
bash -n conductor/webchat/start.sh conductor/webchat/run.sh conductor/launchd/install.sh
plutil -lint conductor/launchd/com.jeff.bob-webchat.plist
curl --noproxy '*' -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/login # 200
curl --noproxy '*' -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/api   # 401
```

The offline suite uses temporary directories and fake providers. The optional
`browser_smoke.cjs` uses Playwright against the live app and makes one real Codex
connection check; it expects `evidence/live-chat.json` from the initial two-turn
check. Set `BOB_PLAYWRIGHT_MODULE` / `BOB_CHROMIUM_PATH` if using a cached runtime.
The initial verification record is `conductor/reviews/WEBCHAT-RESULT.md`.

For the five phone tabs, use the isolated proof from the repository checkout:

```sh
python3 webchat/isolated_tabs_proof.py --output-dir reviews
```

It starts an ephemeral loopback listener with private chats, songs, credentials
and storage. Headless Chromium captures `webbob-tab-<name>-0927.png` for Chat,
Jobs, Songs, Models and Settings, plus the song editor, and tests phone layouts,
stale/unavailable status, duplicate rows, song persistence and logout. Screenshots
use actual responses from that isolated instance, including read-only host
activity; regression fixtures run afterward. It launches no model or worker and
does not restart the live service. Set `BOB_PLAYWRIGHT_MODULE` and
`BOB_CHROMIUM_PATH` when using an existing runtime outside the default paths.
The review and raw evidence are in `reviews/WEBBOB-CLEAN-0927.md` and
`reviews/WEBBOB-CLEAN-0927.tabs-evidence.json`.

## Repeat the live failover drills

Deliberately restart only the webchat server with `BOB_WEBCHAT_DRILLS=1` in the
launcher's environment, then run:

```bash
BOB_WEBCHAT_DRILLS=1 bash conductor/webchat/start.sh
python3 conductor/webchat/live_failover.py --url https://jeffs-mac-mini.tail758ab4.ts.net
```

The launcher will not replace an already running server. The drill uses actual
curl login/POST/poll/Stop requests and real providers on every successful path.
Its private `.drill.json` limits injected failures to the new test conversations
and a separate circuit, preserving ordinary chats. Evidence is written to
`webchat/evidence/failover-live.json`; all-down recovery uses a five-second test
cooldown. It also tests MiniMax, memory, duplicate refusal cards, and replies with
all background lane locks held. The script removes its fault file on exit.
Restart normally afterward so drills are disabled. The broader
`BOB_WEBCHAT_FORCE_FAIL=codex,cursor` environment flag also exists for maintenance
but affects the entire process; prefer the scoped script on a live phone server.

Final failover evidence and architecture review: `reviews/WEBCHAT-FAILOVER-RESULT.md`.

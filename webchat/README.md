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

Status opens `conductor/STATUS.md`; Gemini review opens the saved
`conductor/reviews/LATEST.md`; Jobs shows `screen -ls` and
`next-prompts/INDEX.md`. Reports show their file timestamps. Opening a report
does not request a new model review or change the queue.

## Conversation and provider behavior

Short messages use a fast path (**Gemini → MiniMax → Cursor → Codex → Claude**, a 60s initial budget,
then any untried providers), per the later `WEBCHAT-READY.md` phone brief.
Longer/coding/debug work tries **Codex → Cursor → Gemini → MiniMax → Claude**. Settings can select any of the five
as the first provider; a failed primary falls through to the remaining providers. Codex uses the existing ChatGPT login with API-key environment variables
removed and `forced_login_method="chatgpt"`. No credentials are changed. Native
`codex exec resume <exact-thread-id>` preserves continuity; it never uses `--last`
and therefore never picks up an unrelated coding job. Unsupported/unavailable
saved sessions use recent conversation context. See the official
[Codex non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

Cursor uses `cursor-agent --trust --mode ask --print --output-format json`.
Gemini and MiniMax use `webchat/api_call.py`, which calls the same metered
`services/api.py`/`budget.py` transport as the ask scripts, bypassing background
lane leases. MiniMax has this task's **$59 chat ceiling** (shared budget cap) even if background credit
is increased elsewhere; the child process applies the lower of the chat and shared caps.
Reservations and uncertain calls count toward the cap. Lane health shows that
committed amount, not just settled charges.
Fallbacks receive up to the last 20 messages (24,000 characters) plus bounded, redacted handoff, brain,
status, review and queue snapshots. The provider and fallback reasons appear
beside the reply. An exhausted provider chain produces an honest queued message.
The saved turn automatically retries when a cooldown expires; Stop cancels it.

Codex runs read-only with no approval prompts or inherited user-config MCP tools;
Cursor runs in ask mode. Providers answer, investigate and draft. The separate
confirmed-job handler can queue a draft job; providers cannot invoke it.
Every provider receives the current
handoff and the hard rules: drafts only, no merges/undrafts/force-push, no outward
messages without Jeff's yes to the exact text, no spending/login changes, no
touching Andrea or other workers' edits, and one WebJam coder. Older brain memory
cannot override those rules.

`sessions/<uuid>.json` stores each conversation and its Codex thread ID, mode 600
inside a mode-700 directory. Conversation history survives server restarts.
Login cookies expire after 12 hours and are invalidated by logout or a restart.
An interrupted running reply is marked as interrupted; it is never automatically
replayed. A waiting all-down request survives restart with its frozen context.
Only one reply runs **per conversation** — not globally across all chats (other conversations can reply in parallel). CLI
calls use `chat-<provider>` locks separate from background `lane-*` locks; a busy
CLI slot falls through to the next provider. Handback: `conductor/handback/`
(BOB-STATE in, HANDBACK-LOG out). Say `start a job: …` or `start lane gemini: …` to
queue a durable task. The scheduler claims it, runs a worker, and posts the actual
result back to the originating conversation. Explicit job requests do not need a second
confirmation. Code changes use Codex/Cursor in an isolated draft worktree; nothing merges. Retransmitting the same request ID does not run
the model twice. Confirmed jobs have durable once-only receipts before queue
writes. Ambiguous submissions require checking Jobs; they are never replayed.
Queue writes use the scheduler's queue lock and atomic files.

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

For a deliberate chat restart after tests pass, prefer `bash webchat/safe_restart.sh "tested deploy"`.
It authenticates the idle check and defers during replies or the 30-minute batching window.
For recovery when the service is unresponsive, stop only the `svc-webchat` **server** screen you
started (`screen -S svc-webchat -X quit`), then run `webchat/start.sh`. This signs
out browsers and interrupts an active reply. Other workers are unrelated.

## Phone, MacBook and off-home access: Tailscale Serve

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
Use `run command: uptime`, `run command: pwd`, or `repo status: conductor` for
live mini checks. Repo status also accepts WebJam, StoryBoard, AdoptIQ and shelf.
The command chip supports bounded read-only commands; larger tasks use Start job.
Commands execute without a shell and return a redacted exit-status receipt.
No directory browsing or arbitrary shell/file HTTP endpoint exists. All API
routes require login; mutations also require an unpredictable CSRF token.
Login attempts and request sizes are bounded. Model output is displayed as text,
so embedded HTML cannot execute. Known secrets are redacted from snapshots,
reports and replies; messages containing detected secrets are rejected before
being stored or forwarded. Avoid pasting credentials into chat.

## Verification

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

## September 27 end-to-end regression checks

```bash
python3 -m unittest discover -s webchat -p 'test_*.py'
python3 -m unittest discover -s services -p 'test_*.py'
python3 webchat/e2e_live.py --isolated --output webchat/evidence/e2e-0927-isolated.json
WEBBOB_FULL=1 WEBBOB_BROWSER=webkit node webchat/browser_e2e.cjs
WEBBOB_FULL=1 WEBBOB_BROWSER=chromium node webchat/browser_e2e.cjs
```

The isolated HTTP test injects failures into private temporary conversations while
using real providers for successful replies, including Claude. It never restarts
production or changes production provider health. Browser tests default to the
Tailscale URL and enter the login password from the private local file; credentials
are never printed. Screenshots and raw evidence remain gitignored. Production
launches with drills disabled unless explicitly enabled for a scoped maintenance drill.

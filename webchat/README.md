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

Every message tries **Codex → Cursor → Gemini**. Claude is never in the automatic
route. Codex uses the existing ChatGPT login with API-key environment variables
removed and `forced_login_method="chatgpt"`. No credentials are changed. Native
`codex exec resume <exact-thread-id>` preserves continuity; it never uses `--last`
and therefore never picks up an unrelated coding job. Unsupported/unavailable
saved sessions use recent conversation context. See the official
[Codex non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

Cursor uses `cursor-agent --trust --mode ask --print --output-format json`.
Gemini uses the existing `bin/ask-gemini.sh` with its existing key and metering.
Fallbacks receive up to the last 20 messages (24,000 characters) plus bounded, redacted handoff, brain,
status, review and queue snapshots. The provider and fallback reasons appear
beside the reply. An exhausted provider chain produces an explicit error.

Codex runs read-only with no approval prompts or inherited user-config MCP tools;
Cursor runs in ask mode. Chat is for answers, investigation and drafts; it does
not dispatch coding jobs or send messages. Every provider receives the current
handoff and the hard rules: drafts only, no merges/undrafts/force-push, no outward
messages without Jeff's yes to the exact text, no spending/login changes, no
touching Andrea or other workers' edits, and one WebJam coder. Older brain memory
cannot override those rules.

`sessions/<uuid>.json` stores each conversation and its Codex thread ID, mode 600
inside a mode-700 directory. Conversation history survives server restarts.
Login cookies expire after 12 hours and are invalidated by logout or a restart.
An interrupted reply is marked as interrupted; it is never automatically replayed.
Only one reply runs at a time. CLI calls respect the conductor's shared provider
locks; a busy lane falls through to the next provider. Retransmitting the same request ID does not run
the model twice. Stop and the 180-second per-provider deadline terminate only
process groups started by this chat. Set `BOB_WEBCHAT_TIMEOUT` for a different
deadline (15–600 seconds).

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

```bash
python3 conductor/webchat/test_webchat.py
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

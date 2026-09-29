# Bob web chat — verification result

Verified 2026-09-27T04:38:05+00:00. **The local app is running and tested. Automatic startup is installed but blocked by macOS permission.**

- URL on the mini: **http://127.0.0.1:8787**
- Password location: **`/Users/jeffstory/Documents/bob-overnight-inject/conductor/webchat/.password`**, mode **600**. The password is deliberately absent from this report, source and model prompts. Display it locally with `cat ~/Documents/bob-overnight-inject/conductor/webchat/.password`.
- Server screen: **`svc-webchat`**. The original build screen was renamed `svc-webchat-build` so the actual server owns the requested name.
- Listener verified by `lsof`: **127.0.0.1:8787 only**, server PID **55003** at verification; no wildcard or public listener.
- Start/check: `bash conductor/webchat/start.sh`.
- Source, security and Tailscale runbook: [webchat/README.md](../webchat/README.md).

## Implemented

Python standard-library app under `conductor/webchat/`, messenger history, conversation picker/new chat, typing box, polling provider progress, Stop, dark desktop/mobile layouts. Status renders `conductor/STATUS.md`; Gemini review renders saved `reviews/LATEST.md`; Jobs shows `screen -ls` plus `next-prompts/INDEX.md` and maintenance state. Reports retain their timestamps.

Every message receives “Read BOB-HANDOFF.md + bob-brain/ and act as Bob”, current hard rules and bounded context. Provider order is **Codex (existing ChatGPT login) → Cursor --trust --mode ask → bin/ask-gemini.sh**. No automatic Claude. Codex resumes the exact stored thread ID; fallback receives recent turns. Known credential values are removed before provider calls. Shared CLI lane locks are respected; no coding workers are dispatched by chat.

Sessions are atomic mode-600 JSON in a mode-700 directory. Random login password, unpredictable HttpOnly/SameSite=Strict cookies, logout/expiry, exact Host/Origin validation, CSRF protection, login throttling, bounded requests and subprocesses, cancellation, request deduplication, restart recovery, and plain-text rendering are included. HTTPS Tailscale cookies also use Secure. Private runtime files are gitignored. Chat is read-only/ask mode and drafts only; it does not merge, undraft, force-push or send messages.

## Observed verification

| Check | Observed result |
| --- | --- |
| Curl GET /login | 200 |
| Curl unauthenticated GET /api | 401 |
| Curl valid login | 303 with HttpOnly and SameSite=Strict cookie |
| Curl authenticated session/status/review/jobs/conversations | All 200 |
| Offline webchat tests | **29 passed** |
| Existing services regression suite | **30 passed** |
| Python compile, JavaScript syntax, shell syntax, plist lint | Passed |
| Real Codex conversation and native resume | First turn remembered “amber sailboat”; second recalled it; identical thread ID |
| Real Cursor fallback | Answered “Bob fallback ready.” with Codex deliberately unavailable in the test adapter |
| Real Gemini fallback | Answered “Hi.” with Codex and Cursor deliberately unavailable in the test adapter |
| Browser | Login failure/success, authenticated reports, saved history/reload, actual send/poll/reply, new chat and logout passed; zero page errors |
| HTML injection fixture | Displayed as plain text; no injected element or script ran |
| Mobile | 390×844 viewport, no horizontal overflow; screenshot inspected |
| Actual server restart | Existing password and all conversation file hashes preserved; 200/401 curl checks passed again |

The Gemini live test found that the newly shared helper rejects replies shorter than 20 characters. The adapter now requests a removable response envelope, allowing short answers and separating retry logs from actual replies. A real one-word response and regression tests passed. MiniMax/Gemini design opinions were consulted; suggestions were checked against the implementation rather than treated as verified findings.

Local evidence (private, gitignored) is in `webchat/evidence/`: `unit-tests.txt`, `live-chat.json`, `live-fallbacks.json`, `browser.json`, `curl.json`, `restart.json`, and desktop/mobile screenshots. The offline suite is rerunnable with `python3 conductor/webchat/test_webchat.py` from the Bob root.

## Startup permission still required

The plist exists at `conductor/launchd/com.jeff.bob-webchat.plist`, is installed in `~/Library/LaunchAgents/`, and is loaded as **com.jeff.bob-webchat**. The regular installer includes it; `launchd/install.sh --webchat-only` installs just chat and leaves the other agents alone. The launcher checks once per minute and starts a missing screen.

**Observed blocker:** launchd exit **126**; `logs/webchat-launchd.log` says `Operation not permitted` when `/bin/bash` reads the script under Documents. This is the macOS Full Disk Access gate, not a passing automatic-start test. The terminal-started server works now.

Jeff's next step: System Settings → Privacy & Security → Full Disk Access → add and enable `/bin/bash` (Cmd+Shift+G in the chooser), then run:

```bash
bash ~/Documents/bob-overnight-inject/conductor/launchd/install.sh --webchat-only
```

Check the next `launchctl print gui/$(id -u)/com.jeff.bob-webchat` exit status and curl before claiming login/reboot startup verified. No reboot or permissions change was performed automatically.

## Remote access

**Tailscale Serve is documented, not enabled.** The mini's Tailscale reported Stopped during verification. After connecting both devices, configure the exact origin described in `webchat/README.md`, then use `tailscale serve --bg http://127.0.0.1:8787`. Expected private HTTPS name: **https://jeffs-mac-mini.tail758ab4.ts.net**. It requires the same password. No router ports, Funnel or public exposure were configured.

Updated the canonical `../BOB-HANDOFF.md` and `~/Desktop/HOW-TO-REACH-BOB.md` with local access, password location, provider behavior, startup gate and remote instructions. Existing conductor work and STATUS.md were preserved.

---
name: Start leftover-honest Codex Extra High
description: >-
  use this when Codex is idle and Bob should launch Extra High on one unlocked
  repo so Jeff can watch it in ChatGPT.app; never use exec for a watched job
---
# Start leftover-honest Codex Extra High

Use when Codex is idle and Bob should start Extra High on one unlocked repo. Jeff watches it in ChatGPT.app. Do not use this to merge, send, spend, or touch live Cisco.

## When not to start
- Thread `01a035ac-3e8d-7382-8dc2-c171cf0c5b6f` (`Bob the Bot - CODEX`) is still `active` in `~/.codex/goals_1.sqlite`
- The repo coord issue has `agent` `codex` | `grok` | `claude` and `lease_until` still in the future
- The repo already has an unmerged leftover draft waiting Karen
- Parked PRs, live Cisco, Andrea send, OTP, WebJam tag/signing, Che pull, auto-pitch, auto-post

## How Jeff sees it
Open ChatGPT.app. Thread name is what he clicks. `codex exec` stays unnamed and is **not** listed in the app catalog. Do **not** use `exec` for a job Jeff is supposed to watch.

Bundled CLI (not on PATH):

`/Applications/ChatGPT.app/Contents/Resources/codex`

ChatGPT.app already runs `codex app-server` over `unix:///Users/jeffstory/.codex/ipc/ipc.sock`. Attach to that. Do not start a second app-server.

Extra High is `xhigh` on `gpt-5.6-sol`. Config default `ultra` is one notch above Extra High; pass `xhigh` when Jeff asked Extra High.

## Start a job he can watch
```
CODEX=/Applications/ChatGPT.app/Contents/Resources/codex
SOCK=unix:///Users/jeffstory/.codex/ipc/ipc.sock
"$CODEX" --remote "$SOCK" \
  -C /ABS/PATH/TO/REPO \
  -m gpt-5.6-sol \
  -c model_reasoning_effort='"xhigh"' \
  "PROMPT"
```

There is no CLI `--session-name`. Names come from in-app threads. After a name exists, inject without a second goal:

`"$CODEX" queue --thread 'Exact Session Name' --message '...'`

or `--thread 01a035ac-3e8d-7382-8dc2-c171cf0c5b6f` for the live leftover-honest wave. Queue waits until the current turn finishes. Do not `resume` TUI against a thread the app already holds.

## One leftover, then stop
1. Read the coord issue. Claim a 4-hour `codex` lease with exact SHA and copied holds.
2. Start one Extra High job attached to ChatGPT.app on that checkout only.
3. After a draft PR or honest no-PR, one coord comment, then `agent: none`.
4. Never merge, tag, retag, release, deploy, leftover-squash, or live send from this path. Karen is the leftover + security ship-gate.

## Finish report
`~/.codex/goals_1.sqlite` (`thread_goals.status`), the GitHub draft PR, and the coord comment. Optional last-message file only if the job was `exec` (Jeff cannot see those).

## Prompt contract
Keep the goal short: end state, verified-by, constraints, bounds, parked holds, stop-with-blocker. After the current leftover-honest wave, prefer real product UI/UX/logic/admin/security over leftover theater.

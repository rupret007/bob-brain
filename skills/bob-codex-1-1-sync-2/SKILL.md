---
name: 'Bob Codex 1:1 sync'
description: >-
  use this when Bob and Codex must stay 1:1 in sync via the coord lease board
  with timestamped BEFORE/AFTER deltas as the single shared record
---
# Bob ↔ Codex 1:1 sync

Use when Jeff is running Codex in ChatGPT (desktop/iOS) and Bob cannot reliably inject via `--remote`, or whenever Bob and Codex must share one brain so they do not collide.

## Source of truth
Private `rupret007/Bob-the-Bot` coord issues (one per repo). Body fields: `agent`, `lease_until`, `claimed_scope`, `holds`, `next_action`, `updated`.

**Single shared record for ongoing work:** every meaningful before/after is a **timestamped coord comment** (America/Chicago) plus body field updates. Codex, Grok Clouds, and Bob all read the same issue — never a side chat as truth.

## Before any code change (required)
On the repo’s coord issue, comment one line block:
```
BEFORE <YYYY-MM-DD HH:MM CT>
agent: <codex|grok|claude>
scope: <one leftover or product slice>
base_sha: <exact main/master SHA>
holds: <copied holds>
```
Then set body: `agent`, `claimed_scope`, `sha`/`base`, `lease_until` = now+4h CT, `updated` = now CT.

## After a meaningful delta (required)
Comment:
```
AFTER <YYYY-MM-DD HH:MM CT>
delta: <draft PR URL | honest no-PR | leftover-squash merge SHA | blocker>
tip_sha: <exact>
changed: <short what changed for the next agent>
verified: <tests/CI/holds still true>
next: <Karen | FREE | Jeff gate | still working>
```
Update body fields only. If done: `agent: none`, clear `lease_until`, set `completed_scope` + `next_action: FREE` (or Jeff gate).

## Bob side
1. Every sync beat / before any Grok Cloud: read all open coord issues **and recent BEFORE/AFTER comments**.
2. Mini: `~/.codex/goals_1.sqlite` for `status=active`. If active → paint matching lease; keep Grok off; never second Codex goal.
3. When a draft appears: AFTER comment + Karen leftover+security; leftover-squash only after PASS with tip MATCH main.
4. Idle daytime: try queue into "Bob the Bot - CODEX"; if handshake fails, prepare one paste only when needed.
5. Never use Slack/chat as the state record — always the coord issue.

## Codex side (paste into goals)
Always: read Bob-the-Bot coord issue first (body + latest BEFORE/AFTER). Skip leased/parked/owner-gate. Claim with BEFORE comment before edits. AFTER comment when draft/blocker. Release lease when done.

## Unlock for true inject
Standalone Codex daemon required for Bob `queue` without Jeff paste. Until then: Jeff starts/feeds; Bob owns the board + BEFORE/AFTER discipline.

---
name: Repo coordination lease
description: >-
  use this before working any Jeff GitHub repo — read the Bob-the-Bot coord
  issue first, claim a 4-hour lease, post a delta-only comment after, never
  start a second goal on an unexpired lease
---
# Repo coordination lease

Use before touching any `rupret007` repository for Jeff.

## Source of truth
- Protocol: `COORDINATION.md` on private `rupret007/Bob-the-Bot`
- One open issue titled `coord: rupret007/<repo>` with label `coord`
- GitHub is authoritative. Bob Ops only presents public-safe state
- Do not mix coordination changes into product pull requests

## Before work
1. Read `coord: rupret007/<repo>`
2. If `agent` is `codex`, `grok`, or `claude` and `lease_until` is still in the future, do not start a second goal on that checkout
3. To claim: set `agent` to `codex` | `grok` | `claude`, `claimed_scope` to one leftover or dedicated task, `lease_until` to now plus 4 hours America/Chicago, `updated` to now
4. Record exact SHA, branch, PR when known. No guessed heads
5. Copy `holds` (parked PRs, Jeff-only gates) and do not touch them

## After a meaningful delta
1. Update body fields only
2. Comment one delta (draft PR, honest no-PR, merge, handoff)
3. If done: `agent: none`, clear `lease_until`


## Stale leases
- If `lease_until` is in the past and `agent` is not `none`, clear it in the same pulse: set `agent: none`, clear `lease_until`, note CLAIMED_STALE → FREE with evidence.
- Pausing Mini Shell or AX probes does not pause this. Use GitHub MCP / `gh` from the box.
- Do not start new work on a board that still claims an expired lease as ACTIVE without rewriting it first.

## Public presentment
Private lanes stay high-level. No CSOne, customer rows, secrets, or local paths on the public board. A lease paints as dead text (`Codex lease`) after CI, never as a private-issue link.

## Owner gates
Jeff owns feel, send, spend, live Cisco, Che pull, Logic keys/WAVs. Karen is leftover + security ship-gate. Andrea fence is only `send it` / `send it now` / `send now` in Bob chat.

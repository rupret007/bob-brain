---
name: Multi-agent lease board sync
description: >-
  use this when two or more coding agents (Codex, Cloud/Grok, Claude) may work
  the same repos — reconcile the coordination lease board against real GitHub
  state so each agent skips what is genuinely claimed
---
---
name: Multi-agent lease board sync
description: >-
  use this when two or more coding agents (Codex, Cloud/Grok, Claude) may work
  the same repos — reconcile the coordination lease board against real GitHub
  state so each agent skips what is genuinely claimed
---
# Multi-agent lease board sync

Use before a portfolio-wide or multi-repo wave, and any time two agents could
touch the same checkout. The lease board is the only thing standing between
parallel agents and a collision, so it must never be optimistic.

## The one rule
A lease is a promise about the present. If the board says a repo is claimed and
nothing is actually running, the next agent wastes its wave skipping real work.
If it says free and something IS running, two agents fight over one branch.
**Reconcile against the platform, not against memory.**

## Reconcile each lane
1. Read the lane's coordination issue body.
2. Verify against the platform: current default-branch SHA, open PRs (number,
   draft state, head SHA, mergeable), and the CI conclusion on each head. Never
   carry forward a SHA you did not just read.
3. Set the state honestly:
   - **Claimed** — an agent run is in flight, or a draft PR is awaiting review.
     Name the agent and set a lease that expires (a few hours, not open-ended).
   - **Owner-gated** — review passed but a human must act (a tap-merge, a login,
     a spend, a signature). Release the agent field and make the next action name
     the human, so no agent tries to land or rebuild it.
   - **Free** — nothing running, no open draft. Release it: agent none, lease
     cleared, so the next wave can take it.
4. Carry the holds forward verbatim: parked pull requests, owner-only gates, and
   the never-do list for that product. Dropping a hold is how a parked branch
   gets clobbered.
5. Post one short delta per lane you changed, with real identifiers. Say nothing
   on lanes you did not touch.

## Expire stale claims
A lease whose deadline has passed, or that names an agent with no running job and
no open draft, is stale. Release it. Stale claims are worse than no claims because
they look authoritative.

## Never
- Never mix coordination edits into a product change.
- Never merge, undraft, close, rebase, or edit a pull request during a sync — this
  is a bookkeeping pass only.
- Never invent an identifier, run id, or SHA to make a lane look verified.

## Report
One row per lane: repo, agent, lease deadline, open PR with head and CI state,
who acts next, and SKIP or MAY TAKE for the incoming wave. Then flag every place
the board disagreed with reality, every lane in the wave's list that has no lane
on the board, and any collision the wave's own rules would not catch.

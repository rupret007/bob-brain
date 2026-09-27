---
name: Storyland Fantasy lineup
description: >-
  Use when helping set a weekly fantasy football lineup with the local Storyland
  Fantasy app, including projections, slot proposals, and Jeff-only ESPN
  Move→Here steps.
---
# Storyland Fantasy lineup

## Fence
- Storyland is the local decision brain. It never auto-submits ESPN transactions.
- ESPN Move / Here / Add / Claim / Drop / Confirm are always owner clicks only.
- Do not invent `season.confirm`, advance the local scoring week, clear locks, or edit Week confirmation JSON from chat assent alone.
- Public ESPN default-PPR projections are planning evidence only. They are not the private league’s award, lock, or ownership truth.

## Paths
- App: `Documents/ChatGPT/Storyland Fantasy`
- Start: double-click `Start Storyland.command`, keep Terminal open, then open `http://127.0.0.1:4317/#today`
- ESPN team (Team Rupret): `https://fantasy.espn.com/football/team?leagueId=25015660&teamId=1&seasonId=2026`
- League: La-Z-Boy Legends, league `25015660`, team `1`, season `2026`, eight-team full PPR, priority waivers

## Steps
1. Confirm the real NFL / ESPN scoring week (scoreboard or ESPN My Team week picker). Separately read Storyland’s saved `seasonManagement.week` and `league.currentWeek`. If they disagree, say so plainly and do not silently roll the local week.
2. If Storyland is down on port `4317`, start it with Node via `Start Storyland.command` or `node scripts/start-draft-day.mjs`. Recheck `/api/weekly-actions` and `/api/state`.
3. Load the confirmed roster / initial lineup from Storyland state. Map every starter and bench player by id and position.
4. Refresh public ESPN exact-week projections with the Storyland planning filter (`leaguedefaults/3`, `X-Fantasy-Filter` for projection source 1 and the needed `11{season}{week}` ids). Prefer Storyland’s own evaluators when the local week/receipt/forecast gates are green.
5. Propose a legal nine: QB, RB, RB, WR, WR, TE, FLEX (RB/WR/TE), DST, K. Call out:
   - Thursday/Monday lock order (never stick an early game in FLEX when a narrower slot is free)
   - injury labels as status only, not invented play probabilities
   - gains under one projected point as optional, not automatic churn
   - TE contingency when no rostered TE backup exists
6. Show a short Jeff-only ESPN mirror checklist: open the correct week → Move → Here for slots that differ → verify all nine and the banner. Never drop a player just to mirror.
7. Acquisitions stay a separate owner decision after exact add/drop approval. Research order is not a claim queue.
8. Save dated receipts under a clear folder when useful. Distinguish proposed vs locally confirmed vs ESPN-verified.

## Done means
Jeff has a clear proposed lineup for the live ESPN week, knows which clicks are his, and knows any same-day lock risk (especially TE on Thursday night).

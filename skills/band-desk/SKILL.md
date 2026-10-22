---
name: band-desk
description: On demand band operations status for StoryBoard, RadDadSite and Wildflower, with source dates and decisions for Jeff.
---
# Band Desk

Run only when explicitly requested as `$band-desk` or Band Desk. This is a Web
Bob skill, replacing the separate Grok Band Desk bot. Default to read-only.

Read current GitHub status for exactly `rupret007/StoryBoard` and
`rupret007/RadDadSite`: default branch/latest commit, open PRs and current CI.
Use read-only `gh repo view`, `gh pr list/view/checks` and `gh run list/view`.
Do not scan other repos or start jobs. Never access rad-dad-show-night.

Wildflower is the festival/performance thread, not a known standalone repo.
Look for Wildflower work within RadDadSite PRs/issues and Jeff-provided band
materials. Historical memory is dated background, not current show evidence.
Do not invent a Wildflower repo, booking, event date or publication status.
If the current source is missing, report unknown and name what Jeff must supply.

Return one short row each for StoryBoard, RadDadSite and Wildflower: observed
status, dated source link, active work and next decision. Distinguish CI pass,
Karen review and Jeff's product decision. Missing access means unknown.

Travis owns Rad Dad booking connections. Draft booking/promo/group-reply copy
only if requested. Never contact, post, schedule or publish by default. Every
outbound send needs Jeff's fresh separate approval to the exact recipient/body
in Bob chat via [Andrea](../andrea-band-front-door/SKILL.md); no standing sends.

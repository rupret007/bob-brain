---
name: GitHub music and apps snapshot
description: >-
  Use when the user wants a short status of their music and software projects
  from GitHub, not hardware or parked local folders.
---
# GitHub music and apps snapshot

## Scope
- Source of truth is GitHub, not local disks or old chat.
- Include music and software/app repos only.
- Exclude hardware, 3D print, and closet repos.

## How to gather
1. List the user's GitHub repos.
2. For each music or app repo, note default branch, last commit (title + date in the user's timezone), open PRs, and whether the latest CI on the default branch passed, failed, is billing-blocked, or does not exist.
3. Treat empty one-file README repos as stubs.

## How to write it
- Lead with the live set. One or two sentences per live repo: what is true on GitHub, what is in flight, what needs the user.
- Then a short parked section: only repos that changed since the last snapshot, or one line that the rest are still parked.
- Call out anything that needs the user (merge, billing, a product call). Everything else is held.
- Keep it scannable. No inventory dump. No local-path archaeology.
- Do not merge, push, or start new work during the snapshot unless the user already asked for that in the same conversation.

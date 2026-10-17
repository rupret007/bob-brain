---
name: Stage phone inline lyrics
description: >-
  use this when building a phone stage set list with inline lyrics and wake lock
  for live shows (especially MDM auto-lock phones)
---
# Stage phone lyrics (inline)

## When
Building or refreshing a phone stage set list with one-tap lyrics for a live show, especially when the phone has MDM/auto-lock that kills the screen after opening Drive/Docs.

## Approach
1. Prefer **inline expand** on a single Safari HTML page (lyrics embedded). Do not make Drive Docs the primary tap target if auto-lock/MDM is an issue.
2. Add a **Keep screen awake** button using `navigator.wakeLock.request('screen')` and re-request on `visibilitychange`.
3. Source lyrics from the user’s Google Drive Docs first (search LYRICS folder / known song Docs). External Genius/UG only if no Drive sheet exists, and only if linking to a real lyrics page.
4. Publish via GitHub Gist + `htmlpreview.github.io` for phone access; also save HTML to Desktop when a Mac Mini is available.
5. Paper set list stays separate (big centered titles ± keys).

## Checklist
- Correct set order and keys (band-specific, e.g. Creep in G for Rad Dad)
- One song expanded at a time is fine
- Sticky header + sticky wake button
- Note any missing Drive sheets (placeholder)
- Tell the user when to test: open link → Keep awake → expand a song → wait past lock interval

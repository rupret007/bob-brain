---
name: WebJam ten-second UX gate
description: >-
  use this when checking WebJam Art or Music first-screen UX, or planning Art so
  any artist knows what to click
---
# WebJam ten-second UX gate

Use this before calling an Art or Music pull request ready, and whenever Jeff asks about UI/UX.

## Law
- KISS: if a control needs a paragraph, it does not ship.
- Ten seconds: a painter, sculptor, 3D-print person, songwriter, and talk-only person all know what to click.
- Human words. Delete chrome.
- Music and Art are profiles in one product, not two apps.
- Research a real maker tool before inventing copy. Do not name engines on the door.
- Art is for any artist, not painters only. The room is talk + your own bench. Optional shared canvas is inside the room, not a start card.

## Door
- Art: exactly two start cards, then Host / Join: **Make together**, **Paint along**.
- Paint along keeps the squirrel-with-the-fro face, larger, not named Bob Ross on the card.
- Music: Host / Join only. No New Music Project / local studio on the live door.
- Join is paste the invite. The invite carries what the host started.
- No fourth Art card, no tool picker, no BYOK/provider picker, no chatbot home.

## Follow-along (two valid paths)
- **Webex share is first-class.** People may share a process video in the meeting (YouTube lesson, Bob Ross example). That is a viable option and will often be the one they use. Make together plus that share is enough. Do not talk them out of it.
- **Paint along** is the other option: a silent local file the host already owns or may use, kept in step. Talk stays in Webex. Video stays silent in WebJam.
- Do not put Webex on the door. Do not invent a second video stack. Do not compete with YouTube-in-the-meeting.

## What makes WebJam smoother (on the plan)
1. One question on the door, then Host / Join. No extra cards, no engine names, no settings tour.
2. One next action in the room. Missing file, missing canvas app, missing key: one line after the choice.
3. Let Webex do talk and video share. WebJam is the making room beside it. Two windows, two mutes, one invite. No Embedded App.
4. Keep the artist’s own tools. Procreate, paper, clay, printer, Logic. Do not make them learn a new studio.
5. Invite carries what the host started. Join is paste.
6. Jeff click pass before more door code. Copy-only first.

## Banned on the first screen
Drawpile, Krita, Jamulus, Webex, Moises, Music AI, stems, BYOK, host-clocked, Preview caveats, API, Studio Visit, Bob Ross.

## In the room
- One next action.
- Make together next action is not “open our canvas.” Own-space / clay / printer / paper is valid. Host may open one shared canvas when the group wants to draw together.
- Fail-closed one-liners about a missing local video live after the Paint along choice, in the room.
- AI attaches to native objects only (section, Shared Track, canvas, notes).
- Write-help is this-section / next-section, labeled Suggestion, never a detected fact.
- Stem mute ≠ Jamulus mute ≠ Webex mute.

## Next Art plans
1. Jeff clicks unsigned 0.27.2 Art (ten-second). Write down who gets stuck. No new door code until that.
2. One leftover: in-room any-artist next action (not “open our canvas”), copy-only first. Stay two cards.
3. Keep both follow-along paths. Do not fight Webex share. Paint along stays silent local-file.
4. General smoothness work uses the list above. No fourth card. No second video stack.

## How to check
1. Read the launch copy and start-card tests on the PR branch (`launch_dialog.py`, `creative_modes.py`, `test_art_start_ux.py`).
2. Quote the words a person actually sees. Do not summarize intent.
3. Fail the gate if banned words or extra doors are on screen.
4. Copy-only fixes first. No new features to pass this gate.

Jeff owns merge and feel. Never merge from this skill.

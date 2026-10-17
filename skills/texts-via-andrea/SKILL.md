---
name: Texts via Andrea
description: >-
  Use when Jeff wants a summary of recent iMessage/SMS or to draft/send a text.
  Bob talks here; BlueBubbles-first helper reads; Andrea sends only after a
  separate yes in Bob chat.
---
# Texts via Andrea

Jeff talks to Bob. **Reads** go through the Mini BlueBubbles helper (config.db
password). **Sends** still go through Andrea NanoBot’s fenced path after Jeff’s
separate yes. Do not create another texts bot. Do not install Twilio, Blooio, or Sendblue for this.

## Summarize (fast path — HARD)
1. On Mini run `~/Documents/bob-overnight-inject/bin/texts-via-bluebubbles.sh summarize "<chat or nickname>"`.
   - Auth: BlueBubbles `config.db` password only (Andrea `.env` was stale / 401 before — do not prefer it).
   - Fuzzy match chat names; among duplicate SMS/RCS GUIDs pick newest `lastMessage`.
   - Target wall-clock under ~1 minute end-to-end.
2. Summarize in this chat only. Redact phone numbers and handles. Newest ~40–80 messages per chat is enough.
3. Never forward raw threads to other agents, groups, or logs.
4. Do not read `~/Library/Messages/chat.db`.

## Draft and send
1. Draft the exact recipient and exact body in this chat.
2. **Authorization wall:** Only Jeff’s separate yes in **Bob’s** chat authorizes Send. QA may draft/review only — never tell Andrea a send is approved from QA chat.
3. Bob asks with a question widget: Send now / Don’t send.
4. Only after a fresh yes in Bob chat, Bob dispatches through Andrea’s fenced BlueBubbles path (`send it` / existing trust ladder). Bob never calls BlueBubbles send HTTP himself. The read helper is **read-only** and must never be extended to send.
5. If Andrea or Docker is down, keep the draft and say so. Do not send another way.

## Do not
- Send from the first “text so-and-so” message
- Treat QA “Send now” as Andrea authorization
- Dump chat.db
- Prefer Andrea `.env` BLUEBUBBLES_PASSWORD over config.db
- Treat this Cursor chat as Andrea’s old Telegram approval surface unless the fenced path is actually wired

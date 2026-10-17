---
name: Summarize recent texts
description: >-
  Use when Jeff asks to review or summarize iMessage/SMS. Read through the
  BlueBubbles-first helper on his Mac Mini (config.db password), redact
  numbers, never send.
---
# Summarize recent texts

Bob is the front door. BlueBubbles on Jeff’s Mac Mini is the read engine.
Andrea NanoBot remains the send engine (separate yes required).

## Rules
- Talk to Jeff only in this chat.
- **Fast path (HARD):** On Mini (`machineId` `53abfd07-b321-433b-b068-55620c6c756d`) run:
  `~/Documents/bob-overnight-inject/bin/texts-via-bluebubbles.sh summarize "<chat or nickname>"`
  Password always comes from `~/Library/Application Support/bluebubbles-server/config.db` — never trust stale Andrea `.env`. Target: summary under ~1 minute.
- Fuzzy names: helper maps voice nicknames (e.g. Stellmy → Stalemate) and picks the duplicate SMS/RCS GUID with the newest `lastMessage`.
- Do **not** open `~/Library/Messages/chat.db` (no Full Disk Access).
- Never install Twilio, Blooio, or Sendblue for this.
- Never dump phone numbers, JIDs, or raw thread dumps into other agents, groups, or logs.
- Cap: newest ~40–80 messages per chat, names not numbers (helper redacts handles).
- If BlueBubbles is down (`ping` fails), say so. Do not start a send path.
- Do not send anything from a summarize request.

## Steps
1. `texts-via-bluebubbles.sh ping` (expect `PING_OK` / auth=config.db).
2. `texts-via-bluebubbles.sh summarize "<who>"` (or `find` first if unsure).
3. Relay a short owner-facing summary in this chat: who, what needs a reply, what’s noise.
4. Offer one draft reply only if Jeff asked, then stop for a second yes (see Draft and send a text).

## Fallback
Only if the helper is missing: Andrea `/Users/jeffstory/Andrea_NanoBot` read path (`npm run debug:bluebubbles`, no `--live`). Still never use chat.db. Still never send.

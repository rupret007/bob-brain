# lane-webbob-parity-matrix-0916

You are Claude on Jeff's Mac Mini. Create Web Bob parity matrix. Do NOT use Grok/xAI. No force-push. No Jeff notify/text. No deploy.

## Goal
1. Create `conductor/reviews/WEBBOB-PARITY-MATRIX.md` listing every Bob-the-Bot capability vs Web Bob status. At minimum cover:
   - memory/recall
   - routines
   - dispatch/status of coding lanes + PRs across WebJam / AdoptIQ / StoryBoard / Fantasy / bob-brain
   - multi-LLM workers (Codex, Claude, Cursor, Gemini, MiniMax — never Grok as a lane)
   - texting via Andrea (draft-then-yes)
   - Instinct read/digest/draft (no auto-send)
   - personal todos/reminders
   - file/image attachments
   - voice (live two-way + memos)
   - web research
   - honest status / no empty promises
   - notify rules
   - teammates Karen / Andrea / Band Desk
2. For each row: Bob status, Web Bob status (LIVE / READY / HOLD / MISSING / UNKNOWN), tip SHA or evidence path if known, blocker note.
3. Use existing evidence under conductor/reviews/ (LOOP-RUN-0810-SUMMARY, TEXTING-*, INSTINCT-*, MEDIA-*, GAPS-*, WEBBOB-PARITY-*, live /api/version a777736). Prefer facts over guesses.
4. Queue each MISSING / HOLD-behind-texting item as its own gated feature lane prompt under conductor/prompts/ named like `lane-webbob-<feature>-queued-0916.md` (+ optional .sh stub). Draft-only; NO deploy out of order. Deploy order remains: texting LIVE → gaps → media → voice → UI → Instinct. Do not start those coding screens now — only write the queued prompts/stubs and list them in the matrix.
5. Write a one-line READY marker at the top of WEBBOB-PARITY-MATRIX.md when the file is complete.

## Out of scope
No deploy. No Instinct/gaps/media/voice/UI deploy. No notify. No Grok. Do not touch live webchat.

## Stop
Stop after WEBBOB-PARITY-MATRIX.md exists and queued lane prompts for missing items are written. Print path + row count.

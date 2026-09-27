# Web Bob music handoff (draft)

## In chat today

- **Lyrics / chords / structure:** any automatic provider (Gemini fast path).
- **Song notebook:** Status panel → Song project (persists under `conductor/webchat/song-projects/`).
- **Music demo:** tries MiniMax hosted `music-3.0` / `music-01`, then optional `REPLICATE_API_TOKEN` (music-01), then an honest **local chord sketch** WAV (no vocal AI) when the account is not entitled (HTTP 410). ~$0.04 when a paid route succeeds; local sketch is free. Song panel uses receipt-bound confirm; budget reserves before paid calls only.
- **Uploads:** attach audio in the Song panel (playback in chat). Jeff can describe chords/key/BPM from Moises exports in the message.

## Moises (app today — no Music.ai dev key verified)

1. Process track in Moises (stems, chords, key, BPM).
2. Export chord chart or MIDI/text notes.
3. Upload the mix or export in Web Bob → ask Bob to read structure into the notebook.

## Logic Pro MCP (mini)

Read-only checks only until Jeff confirms. Use existing `logic-pro` MCP tools after verifying the server on the mini.

## Not wired (needs Jeff yes + keys)

- Suno / Udio / ElevenLabs Music / Stable Audio / Music.ai API — research in `reviews/webbob-music-research/`.

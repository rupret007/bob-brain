---
name: Make this song
description: >-
  Use when Jeff says make this song or wants an AI production of a locked
  arrangement. Build the recipe exactly, render MIDI, put the chart in Drive,
  then use Moises on his recordings and Suno only as a record-sounding pass. Do
  not invent form or dump original lyrics.
---
# Make this song

Use when Jeff says "make this song", "make Haunted", or wants a production of a locked Trailer Swift (or other) arrangement.

## Law
- Execute what he said. Do not improve the form unless he asked you to think and recommend.
- If he asked you to think, recommend once, lock a default, and still honor a later override.
- Chords as Nashville numbers in the recipe. Letters are computed from play key + transpose.
- Never paste full original Taylor Swift lyrics in chat or into a generator. Section cues only. Working sheets stay in his private Drive. Vocals only from his boy-narrator sheets.
- Reuse this recipe path. Do not build a second song app. Vault / WebJam / Logic consume the file later.
- No Cloud Agents. No auto-post. No print.
- Jeff away from the keyboard: do not hand over a login. Keep going on recipe, Drive, and already-signed-in Moises.

## Three layers
1. **Recipe / MIDI is the lock.** Form, feel, Nashville numbers, tempo, transpose. This is what "exact specifications" means.
2. **Moises is first-class on his real recordings.** Stems, chords, sections from the 2023 mixes (website, already signed in). Do not treat Moises as a toy sidecar.
3. **Suno (or similar) is the finished-sounding take.** Amazing audio. Not bar-accurate. Cannot take MIDI or a drum map. Style + section tags + his boy-narrator words only. Generate, pick a take, Cover or Replace a section. Never buy credits without him. If Suno needs login and he is away, skip it.

Do not expect Suno to honor 4+4+4 or stop-V2. Those live on the recipe and on Moises-informed edits of his own tracks.

## Recipe schema
One JSON per song, then MIDI:
- source.key, source.tempo
- play.key, play.transpose_semitones, play.tempo_stamp, play.count_grid
- progressions: named lists of roman numerals
- form: list of {id, bars81, feel[], prog}
- feel letters: D double, S single/half-time, X stop, B bridge/other

Count grid is the singer grid (Haunted = 81). Stamp is the Logic tempo (Haunted = 162). One grid bar = two stamp bars.

## How to run
1. Write or update `/workspace/trailer-swift-recipes/<song>.json`.
2. Run `python3 /workspace/trailer-swift-recipes/make_song.py <song>.json <out.mid>`.
3. Put the human chart + MIDI + JSON in the Trailer Swift Drive folder (`1E9J3-gzweRlk9IJlBUR7Nnhr1Zpg8tDw` or the Recipes MIDI folder `1OiR49HEsVzhBs_z8ekklxiB5duKRzMZ-`).
4. If a 2023 mix exists, use Moises on that file (stems/chords/sections). Do not re-upload duplicates.
5. Suno only when he is signed in and asked for a new-sounding cut. No official lyrics in the prompt.
6. Tell Jeff the lock in two or three short bubbles: key, stamp, the one form call that matters, and the Drive / Moises / Suno link.
7. If he says "+2" or "in Em" or "170", change only those play fields and re-render. Do not rewrite the form unless he changed it.

## First song
Haunted is the template. Default: Dm, transpose 0, stamp 162, 4+4+4 is the into-chorus (not the hook), V2 is STOP, after chorus 2 go to the bridge.

The other 12 (10-31-2023) are first-pass form until he locks them. Play keys stay. Tempos are the sped Logic stamps except Dear John (slower).

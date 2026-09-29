# WebJam novice-musician UX punchlist

Written 2026-09-26. Source baseline: `conductor/webjam-ux/repo` at `48007f8`
(branch `codex/ux-max-pass`, stacked on draft #160).

**How this was produced:** read-only synthesis of `INDEPENDENT-AUDIT.md`, `TRIAGE.md`
and `COVERAGE.md`, then re-checked against the source in `repo/`. No paid or API calls
were made in this job (the running `paid_review.py` owner keeps the ledger). No source
was changed. **Not a feel check:** nothing here says the app feels right or is Final
Build ready; Jeff alone judges that. Where an item rests on a screenshot or a headless
runtime check, it says so.

Ranking is by novice impact, then effort (S <= one small commit, M = a few hours with tests).

## Confirmed items (source re-checked at 48007f8)

### 1. Empty error box on the Join page — High impact / S
- **Files:** `webjam_qt/windows/launch_dialog.py` (`_join_error` built at ~950–955;
  `_clear_join_error` ~1186; error paths ~1327, ~1379, ~1406).
- **Observed:** `_join_error` is created with `LaunchError` styling and is never hidden
  (no `setVisible`/`hide`/`show` on it). `screenshots/before/music-join.png` shows an
  empty orange-outlined rectangle between the privacy note and the Join button.
- **Change:** hide the label while its text is empty; show it only when an error is set;
  clear text and accessible description together in `_clear_join_error`. Keep
  `_announce_error` and its focus routing unchanged.
- **User impact:** the first thing a novice sees on Join looks like an error before they
  have done anything.
- **Validation:** pristine Join page (label hidden), invalid paste, typing clears it,
  save failure, ingress error, Back and reopen. Real errors must still appear, be
  announced and move focus. Retake the `music-join.png` screenshot; visual judgment stays
  with Jeff.

### 2. Take Deck playback-failure copy sends people to the wrong place — High / S
- **Files:** `webjam_qt/windows/take_deck.py` (~348–353; output picker at ~144–148,
  accessible name "Take Deck playback output").
- **Observed:** on `PlaybackError` the hint says "Choose another output in Recording
  Setup", but the output selector is in this same dialog beside Play/Stop.
- **Change:** point to the selector in this dialog by its visible label; keep the
  "couldn't open the selected playback output" cause. Inspect how `_on_output_changed`
  retries before wording it as "then press Play".
- **User impact:** a musician who can't hear a take leaves the dialog and hunts in
  another window for a control that is already in front of them.
- **Validation:** inject a player that raises `PlaybackError`, confirm the hint, switch
  output, press Play again.

### 3. Take scrubbers ignore the keyboard — Medium / M
- **Files:** `webjam_qt/windows/take_deck.py` (`_scrub` ~153–159, `_on_scrub_released`
  ~366, `_tick_ui` ~400); `webjam_qt/widgets/recording_studio.py` (~581–583,
  `_seek_from_scrub`). Fix both together.
- **Observed (headless runtime check, INDEPENDENT-AUDIT.md):** pressing End moved the
  slider to 1000 while the player stayed at 0.0 s; the next tick snapped it back to 0.
  Same in Recording Studio. Take Deck's slider has no accessible name; Studio's is named
  "Selected take playhead".
- **Change:** give the Take Deck slider an accessible name; handle keyboard seeks via
  `actionTriggered`/`sliderPosition()` without breaking mouse-drag behavior, and never
  seek from programmatic updates in the tick.
- **User impact:** keyboard and screen-reader users cannot review a take; the control
  visibly moves and silently does nothing.
- **Validation:** arrows, PageUp/PageDown, Home/End, mouse drag, playback tick with no
  recursive seek; test with an injected player, no real device.

### 4. "Legacy two-input Local Original fallback" jargon — Medium / S
- **File:** `webjam_qt/windows/recording_setup.py` `_refresh_tracks_summary` (~583–596;
  Podcast and Review profiles).
- **Observed:** copy says "keep the legacy two-input Local Original fallback (inputs
  1–2)".
- **Change:** reword to say plainly which two inputs will be recorded and what to do to
  choose others. Edit the existing sentence; do not add a dialog or duplicate a summary.
  Keep profile-specific capture scope truthful.
- **User impact:** "legacy" and "fallback" read as a warning and tell a novice nothing
  about what gets recorded.
- **Validation:** all three profile branches render; wording matches
  `core/session_recording_plan.py` behavior.

## Candidates needing verification before implementation

| Item | Impact / effort | Files | What to check first |
| --- | --- | --- | --- |
| Identity not visible after committing to Join | Medium / M | `launch_dialog.py`, session HUD | Music/Art identity is hidden on choice and Join; a novice can't confirm what bandmates will see. Show it after Join or in session; keep the clean first door. Queued as backlog item 17. |
| Export success message is dense and technical | Medium / M | `core/studio_export.py`, `core/take_export.py` and their widgets | A simpler receipt must keep the edited vs originals-only distinction and not imply publication. Related to item 23 (recording receipt export). |
| Unsaved-edit notice on workspace switch | Low–Medium / S | `recording_studio.py`, `application_controller.py` | Audit says this is **not** data loss (dirty state is retained, `prepare_close` gates). Only add a notice after checking the real switch/close callers. |
| Announce current playback errors | Low / S | `recording_studio.py` | Make current errors announced; never show errors from an obsolete playback epoch. |
| Supplemental core-copy coverage | Process | `core/host_startup_checklist.py`, `creative_modes.py`, `provider_credentials.py`, `jamulus_name.py`, `meeting_link.py`, `rehearsal_recap.py`, `session_*.py` | These supply visible copy and were outside the first manifest. `supplemental.json` (passes 197–220) covers most; `meeting_link.py` still needs a coverage check, and truncated passes 001/004 need usable replacements. |

## Do NOT implement (rejected after source checks)

Council agreement is not evidence; these were accepted by at least one model and are wrong.

- "Install Jamulus to host" for the disabled Music Host: the platform reason
  ("Hosting needs the macOS app. You can still Join.") already exists.
- Running a checksum-failed installer as administrator: the refusal is deliberate.
  Safe copy only: download WebJam again from its official source, then retry.
- Renaming every private room "Remote Jam": invitations can lead to Art, Podcast or
  Review; tests pin the neutral "Room".
- Keeping a raw private invitation after a save failure: disposal is deliberate and tested.
- Requiring a pasted invitation to "look like a link": the whole message is accepted.
- Blanket "Ready to jam!", "Jamulus" or "jam name" HUD wording: the HUD serves other
  profiles; the controller owns state copy.
- "Copied!" set by the view: the controller writes the clipboard and confirms on success.
- A modal `QMessageBox` after Save in Recording Setup, and any text implying a take is
  recorded without local originals.
- Global Enter/Escape shortcuts (`returnPressed` is already wired; risk of double
  submit or unexpected close), adding explicit button accessible names alone, and
  cancel-on-hide for exports.
- Waveform-error reassurance ("will play and export normally") and "aligned to the
  beat": both unsupported by the code.

## Open blockers

- No worktree was assigned to this job, so `STATUS-NOTE.md` is written beside this file.
- Items 1–4 are unimplemented. The scheduler picks the coder; one WebJam coder at a time.
- Any implementation should start with items 1 and 2 (smallest, highest novice impact).

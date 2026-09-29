# Independent source validation

2026-09-26, secondary Codex session. The already-running `svc-webjam-ux` session
remains the sole coder. This audit changes no application source, launches no paid
reviews, and does not take over its branch, ledger, manifests, or status document.
Baseline inspected: `5bddcd240136f5655853f63bf7d8c7992ea82e82`.

## Confirmed improvement candidates

| Impact / effort | File / location | Change | Evidence and acceptance |
| --- | --- | --- | --- |
| High / S | `webjam_qt/windows/launch_dialog.py`, `_build_join_page`, `_clear_join_error`, the three error-display paths | Hide the Join error label while empty; reveal it only when displaying an actual error. Clear its accessible description with the message. | `screenshots/before/music-join.png` shows an empty orange-outlined rectangle between the privacy note and Join. The label is given `LaunchError` styling and never hidden. Verify pristine Join, invalid paste, typing to clear, save failure, ingress error, and Back/reopen. Preserve real errors and focus routing. |
| High / S | `webjam_qt/windows/take_deck.py`, `_toggle_play` | Point playback failure recovery to the existing **Output** selector in this dialog, using that exact label. | MiniMax pass 015 issue 2 is confirmed. `_output_picker` is built immediately next to Play/Stop, but the failure text sends users to Recording Setup. Trigger a `PlaybackError`; select a different output and retry without leaving the take. |
| Medium / M | `webjam_qt/windows/take_deck.py`, scrub slider construction and `_tick_ui` | Give the slider an accessible name and support keyboard seeking, with no seeking from periodic programmatic position updates. | `_scrub` has only `sliderPressed`/`sliderReleased` connections. Arrow/Home/End actions change slider position without releasing a mouse drag, so `_on_scrub_released` is not the keyboard path. Consider `actionTriggered` with `sliderPosition()` for keyboard actions, preserving mouse drag behavior; verify arrows, PageUp/PageDown, Home/End and no recursive seek during polling. Explicitly test with an injected player before claiming fixed. |
| Medium / S | `webjam_qt/windows/recording_setup.py`, `_refresh_tracks_summary` | Replace implementation terms such as “legacy two-input Local Original fallback” with a short explanation of which two inputs will be recorded. | Default-input information is already present. Improve the existing sentence rather than adding a confirmation dialog or duplicating a summary. Keep profile-specific capture scope truthful. |
| Medium / S | `webjam_qt/windows/simple_settings.py`, `show_optional_keys`, `showEvent`; called by `application_controller.py` around line 12723 | When opened specifically for optional keys, scroll to and focus that section after layout. Follow the existing meeting-link focus pattern. Keep ordinary Settings opening on the musician name. | Runtime reproduction at the default 640×560 size: `show_optional_keys(); show()` expands the section but leaves scroll value 0 and focus on “Your musician name”; the section toggle starts at y=455 in a viewport only 456 pixels high. The key controls remain below the fold. Check both a fresh dialog and an already-visible one. The existing test only checks the expanded state, so add a visibility/focus assertion for this entry route. |

## MiniMax findings that must not be accepted literally

| Finding | Source validation / disposition |
| --- | --- |
| Pass 002 issue 1: disabled Music Host has no reason; suggest “Install Jamulus to host.” | **Reject.** `_music_host_unavailable_reason()` returns `WIN32_MUSIC_HOST_REASON`, which is already “Hosting needs the macOS app. You can still Join.” `_can_host()` explicitly gates Music hosting to macOS. Installation does not remove that platform restriction. |
| Pass 002 issue 3: retry an installer that failed integrity checks as administrator | **Reject this remedy.** `_install_jamulus()` deliberately refuses a checksum mismatch and clears the installer path. Plain replacement copy may say “The included installer could not be verified. Download WebJam again from its official source, then try Install Jamulus.” Never imply elevation repairs a failed integrity check. |
| Pass 002 issue 4: an empty `CreatorStart.detail` yields a broken description | **Not established.** `CreatorStart.__post_init__` validates `detail` using `_text`, which rejects empty content. Formatting cleanup is optional, not a confirmed accessibility defect. |
| Pass 002 issue 5: pasted text must “look like a link” | **Reject that requirement.** The UI intentionally accepts the whole invitation message. Keep “Invitation pasted — choose Join”; validation belongs to ingress, and “pasted” makes no validity claim. |
| Pass 003 issue 2: rename every private remote room “Remote Jam” | **Reject.** `RemoteInvitation` carries no room title and can lead to Art, Podcast, or Review. `tests/test_art_cold_invitation_context.py` checks the neutral “Room” title before authenticated profile information arrives. |
| Pass 003 issue 3: retain a raw private invitation on a save failure | **Do not implement as written.** Raw private invitation disposal is deliberate and tested in `tests/test_remote_launch_ingress.py`. Any retry UX must preserve credential lifetime boundaries; deleting one `clear()` also does not restore a value already cleared earlier. |
| Pass 008 issue 2: set every `ready=True` HUD to “Ready to jam!” | **Reject.** The controller supplies the status and detail for each state. `ready` is a presentation flag also used for recording and other profiles. Replacing controller copy can claim audio readiness from weaker evidence and erase specific instructions. |
| Pass 008 issue 4: set “Copied!” after emitting the invitation signal | **Reject.** The view does not know whether copying succeeded. The controller already writes the clipboard and shows a seven-second confirmation after success (`application_controller.py`, around lines 7660–7706). A view timer could also overwrite a later state. |
| Pass 008 issues 5, 6, 8: use “Jamulus” / “jam name or ID” for generic HUD actions | **Reject blanket replacements.** The HUD also handles Art, recording, recovery, and optional meeting links. The controller already passes a meeting-specific input placeholder and contextual actions. |
| Pass 014 issue 2: use checkbox text “Capture local audio” | **Verify exact labels first.** The chunk did not contain the checkbox construction, so the claim that this label was verified is unsupported. Recovery must match the actual visible control. |
| Pass 014 issue 5: add a “non-blocking” `QMessageBox.information` after Save | **Reject as proposed.** This call is modal, and the local-capture-off copy would incorrectly imply no recording is possible without local originals. Prefer existing inline scope/next-step feedback. |
| Pass 014 issue 6: the default two channels are silent | **Reject missing-feature claim.** `_refresh_tracks_summary()` already describes default two-input capture for each profile. The wording can be simplified. |
| Pass 014 issue 7: `_sync_capture_fields()` refreshes stale channel counts | **Reject rationale.** That method manages visibility and clears errors; channel counts are handled by `_refresh_tracks_summary()`, which is already called after editing tracks. |
| Pass 015 issue 3: absence of an explicit button accessible name makes Play stay stale | **Not established.** Native QPushButton accessibility can derive its name from current text. Adding explicit names requires updating pause, stop, failure, take selection, and natural completion together; verify the accessible interface rather than assuming. |

## Coverage checks for the review owner

The initial manifest has 105 files and 196 chunks. It covers every tracked Python
and QSS file under `webjam_qt` except explicitly excluded package/build helpers.
However, a fixed core allowlist misses some source files that supply visible copy.
These deserve supplemental code-and-context passes before declaring all user-facing
strings reviewed:

- `core/host_startup_checklist.py`: the first-run HUD checklist, profile note, and
  disabled Music Host reason. The missing constant already caused pass 002's false
  positive.
- `core/creative_modes.py`: profile names, first-screen activity cards, summaries,
  descriptions, quick help, capability contracts, and Studio presets.
- `core/provider_credentials.py`: provider purposes, key placeholders, key status,
  and save-validation messages surfaced by `webjam_qt/widgets/provider_keys.py`.
- `core/jamulus_name.py`: user-facing validation errors shared by launch/settings.
- `core/meeting_link.py`: capture-scope notices and meeting validation messages used
  across Music, Podcast, recording, and settings.
- `core/rehearsal_recap.py`: take status and duration labels in the end-of-session
  recap.
- `core/session_conductor.py`, `core/session_health.py`, and
  `core/session_intelligence.py`: check emitted presentation/action/status strings
  and include their relevant chunks; a widget review alone cannot validate these.
- `ios/Sources/ArtCompanionCore/CompanionModel.swift`, `Invitation.swift`, and
  `RoomSummary.swift`: connection/retry/paused text, `CompanionError.description`,
  and activity labels displayed by `ios/ArtCompanion/ArtCompanionApp.swift`. The
  initial inventory selects only `ios/ArtCompanion/` and `ios/PocketStage/`, so
  these directly visible strings fall outside it.
- `core/studio_project.py`, `core/studio_sections.py`, `core/studio_comping.py`,
  and `core/studio_controller.py`: selected typed errors reach musician-facing
  text through `studio_messages.safe_detail`. Reviewing that formatter alone
  does not review the actual sentences. Prioritize user-triggerable edit errors
  rather than internal invariant diagnostics.

Review the other excluded core/service error sources where controllers display
their exceptions verbatim; avoid treating all backend implementation files as UI.

The Qt `FirstRunSetupDialog` and `SetupWizard` classes have no references from the
current runtime's `webjam_qt` callers beyond their own definitions. Their tests and
legacy counterparts are not evidence that a new musician sees them. Complete the
requested file reviews, but rank these dormant flows below verified defects in
the actual Host/Join, Settings, Recording Setup, and Studio routes.

## Accounting and review validity

The ledger is locked and uses response token counts, with unsettled requests kept
at their reservation. Rates match MiniMax's published standard M2.7 prices:
$0.30/M input and $1.20/M output; reservations allow $0.375/M cache-write input.
Source: https://platform.minimax.io/docs/guides/pricing-paygo (checked 2026-09-26).
The $48 admission cap leaves a margin under the user-authorized $50.

At this audit's first check, passes 001 and 004 were truncated and correctly marked
incomplete. Their files existing must not count as source coverage. Follow-up
passes should retain the original paid attempts in the ledger and map valid
replacement results to the original file/chunk. The runner skips existing result
files, including incomplete ones, so a separate retry/replacement manifest is
needed. This is a task-local spend estimate; unrelated conductor usage is not an
account-balance measurement.

## Follow-up source and runtime checks

- The existing review owner has independently added `supplemental.json` (passes
  197–220), covering most of the core-copy gaps above, and `retries.json` with
  explicit replacement mappings. `core/meeting_link.py` still merits a coverage
  check. This is progress on the original inventory, not completed coverage until
  usable responses exist.
- A headless runtime check using the existing `TestTakeDeck` synthetic WAV helper,
  injected player, and patched empty device list confirmed the keyboard scrub
  defect: pressing End changed the slider to 1000 while the player stayed at 0.0
  seconds (duration 0.5 seconds); the next `_tick_ui()` returned the slider to 0.
  The slider's Qt accessible name was empty. No real output device was opened.
  The integrated `recording_studio.py` uses the same release-only slider wiring
  at lines 582–583, so verify/fix both controls together.
- A second synthetic-take runtime check confirmed the same failure in the
  integrated Recording Studio: an enabled slider reached 1000 on End while the
  player remained at 0.0 of 1.0 seconds, then snapped to 0 on `_tick()`. A separate
  native-accessibility check returned `Pause` after setting button text to Pause
  and leaving its explicit accessible name empty. This confirms that absence of
  an explicit accessible name is not, by itself, a stale native-button name bug.
- Qt's official `QAbstractSlider.actionTriggered` documentation confirms that
  `sliderPosition()` already reflects the user's action while `value()` has not
  propagated yet. A keyboard seek handler on this signal should read position,
  and retain the distinction between user actions and periodic `setValue()`.
  Reference: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QAbstractSlider.html#PySide6.QtWidgets.QAbstractSlider.actionTriggered
- Pass 020's proposed waveform-error reassurance, “will play and export normally,”
  is unsupported: preview failure does not prove playback/export success. Keep
  the source-verification boundary. Likewise, “aligned to the beat” is not an
  equivalent description of time-aligned originals imported together at 0:00.
- Pass 023 issue 2's claim that a tab switch cancels export is false in the shown
  source: `hideEvent` flushes Studio edits and stops playback; it does not call
  `shutdown()` or cancel export. Do not add a confirmation gate for that invented
  behavior. The MP3 example is also not evidence of the WAV export path here.
- Pass 023 issue 1 overstates the observed failure as lost recorded audio.
  `_flush_studio_state` persists Studio edits, and the original recording is a
  separate artifact. `test_studio_autosave_failure_stays_dirty_and_retries_without_losing_edit`
  checks retained dirty state and refused shutdown on failure. A visible global
  unsaved-edit notice on workspace switching may still help, but verify the
  actual switch/close guard before classifying it as data loss.
- Pass 023 issue 4's suggestion to show an older-epoch playback error after a new
  run has started would undermine stale-result handling. Improve announcement of
  current errors without surfacing failures from an obsolete playback generation.

## Council validation

`council/gemini-onboarding-recording.md` is a complete response, but it accepts
several findings contradicted above: running a failed-integrity installer with
elevation, renaming all private rooms “Remote Jam,” retaining cleared raw private
invitations, and requiring a pasted whole invitation message to look like a link.
It also accepts the empty-`CreatorStart.detail` premise despite the constructor's
nonempty validation. Council agreement is not a substitute for the cited source
checks. The final punch list should reject these exact remedies even when one
review model labels them ACCEPT.

## Additional rendered evidence

`screenshots/independent/recording-setup-empty.png` and
`screenshots/independent/first-recording-choice.png` were captured with synthetic
settings, an empty mocked input-device list, and a no-op credential store. No
settings were saved and no audio, installer, or network action was triggered.

Recording Setup displays its entire channel-map paragraph while optional local
capture is unchecked, and shows an unchecked “Use 48 kHz and automatic buffer”
immediately below a status that already says 48 kHz / Automatic. A useful modest
polish is to explain the optional action in plain language and label the format
checkbox as an explicit reset-on-save action, without changing capture consent or
pretending it controls Jamulus. Keep the live/recording boundary in concise help.

The optional-key panel saves/removes credentials immediately, independently of
the enclosing Settings Save/Cancel. `storage_note()` explains storage location but
not this timing. Add a sentence such as “Save key and Remove take effect
immediately.” next to those controls; do not move secrets into the settings draft
or imply Cancel reverses those explicit actions.

## Branch preservation verification

Read-only GitHub checks confirmed all three existing PRs remain open drafts:
#158 `b11a7c4`, #159 `86c9a30`, and #160 `5bddcd2`. The existing run's discovery
receipt discloses a temporary accidental advance of #159 and a normal corrective
commit; do not hide that history or force-push it away. The new UX branch starts
from #160's preserved head. The original outside-workspace checkout remains dirty,
but its tracked one-line fix is represented in remote #160.

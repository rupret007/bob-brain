# Codex verification notes (source review; no feel claims)

## Confirmed candidates
- Empty Join error label is visible before an error and renders an empty outlined box (screenshots/before/music-join.png). Hide unless nonempty; keep errors announced and focusable as appropriate.
- Music/Art identity is hidden on choice and Join; settings can show/edit it, but novice cannot verify what bandmates will see before joining. Surface after committing to Join / in session, preserving clean first door.
- Take Deck scrub slider has no accessible label; playback-error remedy points at Recording Setup even though Playback output is in this same dialog. Inspect playback wiring before changing wording.
- Export success is a dense technical hint. It has an existing reveal button; simpler receipts must preserve edited versus originals-only and unverified publication boundaries.

## Reject or narrow before implementation
- pass-003 missing Return shortcut: false positive. _invite_input.returnPressed already connects to _join. Qt QPushButton default/keyboard behavior exists. Do not add global Enter/Escape shortcuts that could submit twice or close unexpectedly.
- pass-002 disabled host has no reason: false positive for current supported platforms. _host_reason exists and tests assert it.
- Missing explicit QPushButton accessibleName alone is not a defect: Qt derives its label from text. Dynamic custom names can be a defect only if stale.
- Keep invitations masked and memory-only. Do not restore bearer tokens after failure without auditing one-use semantics. Do not change generic Room to Remote Jam for every profile.
- Studio hideEvent does not itself prove data loss. ApplicationController has a prepare_close gate and Studio retains dirty state for retry. Validate navigation callers before changing anything; QHideEvent.ignore is not a safe cancellation design.
- Exports remain active while hidden unless source/recording lifecycle cancels them. Do not add a cancel-on-hide behavior on the strength of a reviewer assumption.
- Audio settings, devices and live capture are not owned by WebJam's launch door. Preserve dedicated Jamulus profile and evidence boundaries.
- Gemini 2.5 Flash first council overaccepted findings, mislabeled copy problems P0 and proposed unsafe/incorrect statements (for example Stop discards a take; a meter absence still records). These recommendations are not implementation authority. A stronger Gemini 3.1 Pro critique plus Claude and local verification will arbitrate.

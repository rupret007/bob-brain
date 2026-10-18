# Bob's brain (backup)
Everything Bob the Bot knows and can do, for use by Claude/Codex if Bob is out of usage.
- skills/ : every saved skill (each folder has SKILL.md = a how-to recipe)
- memory/ : Bob's memory about Jeff, projects, rules
- user-memory/ : facts shared across all of Jeff's assistants
- automations/ : saved routine prompts (automation.json "prompt" field) - most are paused
- profile.json : Bob's role
Start: read ~/Documents/bob-overnight-inject/BOB-HANDOFF.md first, then use this repo as reference.

Web Bob releases go on the coord board. Every proposed release must have an
owner, current resource claim, draft PR, exact commit SHA, test/product evidence,
Karen's verdict for that SHA, and Jeff's approval recorded there before activation.
Keep BOB-HANDOFF.md as a linked narrative handoff; it is no longer an alternative
to a coord release record. This explicitly supersedes the board's older exclusion
of Web Bob releases. Web Bob stays draft-only; merges require Karen PASS for the
current SHA and Jeff's standing approval. See [release contract](docs/release-board.md).

Local StoryPool services (draft, activation needs Jeff):

- [Andrea reply adapter](docs/andrea-local-replies.md): Web Bob drafts @andrea
  replies; every send requires fresh separate Jeff approval to the exact draft.
- [$band-desk](skills/band-desk/SKILL.md): on-demand StoryBoard, RadDadSite and
  Wildflower status.
- [$director](skills/director/SKILL.md): on-demand music video direction notes.
- [$stack-ops](skills/stack-ops/SKILL.md): on-demand local stack/dashboard and
  NEEDS_JEFF observations. `python3 -m webbob.storypool_status` is read-only.

The three skills require explicit invocation and default to read-only work.

The go-live candidate's remaining integration work is tracked in [GAP_LIST.md](GAP_LIST.md).
[SHARED_CONTEXT.md](SHARED_CONTEXT.md) describes the shared Mini journal and bounded
live-source readers. These candidate changes do not activate Web Bob or authorize sends.

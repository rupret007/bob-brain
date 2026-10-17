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

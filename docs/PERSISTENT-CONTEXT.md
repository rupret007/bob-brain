# Persistent project context

The private project store extends Web Bob's existing memory directory and atomic
I/O. It does not migrate personal notes, add a scheduler or grant work permission.

Start with `For the Atlas project, remember the priority: clear answers. Keep delivery working.`
An immediate `Correction: continuity comes first.` replaces the same priority
subject while retaining other constraints. For a later change, name the project
and fact category again. A uniquely named project selects context for later
follow-ups; an explicit topic change suspends it until the project is named again.

Settings → Saved memory → Project context shows current owner facts and source
references. Review removal selects one exact fact at a project revision; a separate
confirmation removes it. Earlier cards become stale after another turn. Removal
stops future retrieval as current context; it does not erase historical transcripts,
past provider input or separately held copies.

`memory/projects.json` schema1 contains stable project/goal IDs, current fact
subjects, revisions, owner source references and timestamps. Removed facts retain
a tombstone without their old value. The private revision audit records identity,
not a second copy of superseded text. A source user turn and exact intent commit
before the store change; restart observes its receipt, restores the revision
outbox and never repeats an uncertain write. Outbox events contain IDs/revisions,
not private fact values. Ordinary model answers carry server-owned dependencies;
later corrections suppress stale dependent prose from model context while
preserving the visible transcript. Voice tool results carry the same dependencies.
A voice call with changed project context ends on its next server interaction and
must restart for a fresh context snapshot; transcript flushing remains possible.

Relevant projection is capped at6500 UTF-8 bytes, with explicit omitted IDs and a
source pointer. Prompt assembly adds it independently of operational snapshots,
so ordinary conversational answers can use it without loading the whole journal.
Context is source data, never permission. Task ownership, holds and effects remain
owned by the existing queue; the report/handoff contracts are separate work.

The coordination direction is one conductor, exposed through Web Bob, with one
accepted owner per assignment. A provider answers or executes its bounded task;
it does not silently become another release owner or start competing work.
Capability observations distinguish supported operations, authentication, reach,
freshness, billing and unknown quota. Use more resources when their distinct work
helps the objective; simultaneous activity alone is not progress. Quality evidence
must support a route choice before it replaces an established capable route.

This foundation uses the existing queue and journal, not a second scheduler.
Bounded report work currently has one qualified adapter design (Claude); real
subscription execution and report quality still need release-specific proof.
Dot/Grok exports remain prepared and unaccepted until an actual receiver returns
bound evidence. Acknowledging history does not execute it. Automatic native
dispatch, continuously verified capacity and broad capability-based scheduling
are not established by this milestone's local context or handoff contracts.

Reuse review: Andrea's qualified83623dd8 source includes `grounded-memory.ts`
(`reconcileGroundedMemory`, `buildGroundedContextBundle`) and
`durable-work-continuity.ts`. Their useful semantics—explicit source types,
superseded/terminal records, bounded retrieval and `executionAuthority:false`—
inform this compatible Web Bob implementation. No Andrea database or orchestration
runtime is imported. No external context bridge or native collaborator acceptance
is implied. Any future exchange must bind owner/project, source version, freshness
and receipt identity rather than reading Andrea's broad unscoped diagnostics.

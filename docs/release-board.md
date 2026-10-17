# Web Bob release coordination contract

Web Bob releases go on the coord board. This is the explicit contract migration
requested by Jeff; it supersedes the older `coord/README.md` sentence that left
Web Bob releases only on BOB-HANDOFF.md. This PR changes the repository rule; the
external coord README and live handoff are untouched by this task's sandbox.

Each proposed release records repository, owner, current claim reference, draft
PR number, full SHA, status, evidence references, Karen receipt, Jeff approval
receipt and narrative handoff link. Status is PROPOSED, BLOCKED, APPROVED,
RELEASED or ROLLED_BACK. PROPOSED/BLOCKED may have pending approval receipts.
APPROVED/RELEASED must reference both approvals for the exact SHA. A schema-valid
record is not authority: the trusted executor still verifies current ownership,
evidence, Karen PASS, Jeff approval and the parity gate immediately before acting.

Use the existing coord authority; do not create a second release ownership store.
Write only your own append-only records and retain prior events. Link the latest
coord release record from BOB-HANDOFF.md when an authorized release actually
occurs. Do not rewrite older agent notes, conductor journals or claims.

Web Bob remains draft-only. Never merge, undraft, force-push or treat old QA as a
new commit's approval. Jeff's standing merge approval and Karen's exact-SHA PASS
are mandatory for merges; this rule does not make either approval exist.

`validate_release_record` catches missing ownership/evidence and approval SHA
drift before a record is posted. Tests cover those failures and ensure a valid
proposal cannot mint execution authority. No actual release record or live
activation was performed in this change.

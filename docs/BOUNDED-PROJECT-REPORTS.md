# Bounded project reports

After saving a Web Bob project priority, an owner can ask:

> Create a read-only Web Bob readiness report.

The product selects bounded source excerpts and current owner context, saves the
exact assignment before queue admission, and assigns Claude through its supported
subscription login. This route permits one execution attempt of at most 900
seconds. It disables model tools, MCP, plugins and slash commands, uses high
effort with the requested Opus model family, and rejects unexpected model/tool
events. Managed policy must pass the local admission check. It never silently
falls back to an API key or another worker.

Claude's final model and usage fields are retained. CLI dollar figures are
estimates, not proof of invoice charges. Subscription login does not prove
remaining allowance or guarantee that extra usage cannot apply; those remain
explicit unknowns. The CLI's one-dollar estimate ceiling is additional exposure
control, not an invoice guarantee.

Reports cite supplied sources and disclose bounded coverage. The server verifies
the assignment, source hashes, citation membership and saved artifact. These
checks do not independently certify every finding's semantic accuracy. Human
quality review and the release's realistic workflow proof remain required.

> Create a read-only next-actions brief for Web Bob from report JOB_ID.

The second assignment reads the checked original report and latest owner context.
If no job ID is supplied, it uses the latest completed report for the selected
project. Old report findings are historical; current corrections take precedence.
Source collectors for other projects need an explicit reviewed implementation.

Hold/resume preserves the original assignment, evidence and task ID. A changed
project revision prevents execution of a stale held assignment; it is not
silently rewritten or replaced. Cancellation fences late results. A crash after
execution consumes the one attempt; recovery observes that failure rather than
rerunning a provider. Imported or quoted instructions do not authorize work.

The authenticated Jobs result contains the report and its integrity status.
Results live under `conductor/state/project-reports/<goal-id>/<task-id>.md`.
Input bundles are private and immutable under `conductor/state/project-report-inputs`.
The coordination journal records report IDs and hashes, not private report text.

## Owner-relayed review

After a report completes, ask “Prepare a review handoff of report JOB_ID for Dot”
(Grok and Claude are also supported recipients). The conversation provides a
download containing the exact report, current project context, holds, observed
tasks, a bounded journal page and an empty return-format template. Preparation
does not contact the recipient, acknowledge history or transfer task ownership.
An ordinary request to draft a handoff from supplied findings remains normal
conversation and does not require a completed executor report.

Use **Import returned review** to load the receiver's filled JSON response. The
server requires the original handoff/source identities, exact current context
revision and content hashes. It rejects stale, mismatched and conflicting
duplicate artifacts. An exact duplicate returns the same durable receipt. Saved
payload digests are rechecked on export and retrieval. The response remains
`returned_unverified`: source binding is verified, claimed authorship is not.
Import cannot start a task, ACK Grok, grant Dot write access or certify completed
work. Imported text is excluded from ordinary model context.

## Resource observations

Resource questions receive supported capabilities alongside a bounded projection
of `conductor/state/resource-inventory.json`. Each account observation has its
own timestamp; after 15 minutes it is marked stale. Remaining allowance stays
unknown when the provider did not expose it. A nested usage snapshot retains its
own observation time. The inventory does not start login flows, generation or
workers. Explicit execution, account funding and quality checks still govern
each actual assignment. Reducing Cursor may reduce Grok Bot allowance; a savings
recommendation must preserve that dependency and measure representative use.

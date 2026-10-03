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

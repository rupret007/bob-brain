# Workspace read-first integration (P4)

**needs Jeff: OAuth consent + scopes**

Use the MIT community server `taylorwilsdon/google_workspace_mcp`, pinned at
`789730452b9c5452b2c8d348cf005d196c12ba4e`. No replacement Google HTTP/OAuth
client is introduced. Source: https://github.com/taylorwilsdon/google_workspace_mcp.
The upstream `auth/scopes.py` defines the base identity scopes; its permissions
mode narrows services to Gmail, Calendar and Drive read-only. The checked launch
configuration is in `config/workspace.json`. Do not launch it until Jeff consents.

Exact initial scope list:

- `openid`
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/userinfo.profile`
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/calendar.readonly`
- `https://www.googleapis.com/auth/drive.readonly`

No OAuth flow, login, callback listener or account probe was run. The local
facade raises the needs-Jeff status before invoking any tool unless the trusted
host supplies a consent-verified session. Model arguments cannot select another
account. Gmail search/read, Calendar get-events, and Drive search/read are the
only read tool names allowed. Returned evidence retains tool, arguments, fetch
time and a bounded body for the existing conversational daily-brief renderer.
Private Workspace content must never feed the shared-facts importer implicitly.

Email and event drafts are local private records with exact payload, account,
conversation, revision, expiry and digest. Any edit changes the binding. Reuse
the existing texting/calendar consent-card verifier through `verify_consent`;
the supplied verifier must consume exact authorization, not a model boolean.
Use P1's protected ownership context for `ownership`. Neither callback has an
allow-all default. No raw write tool is exposed through the read facade.

Writes remain disabled. Enabling them later requires separately reviewed scopes
and tools. Minimum Google API additions for the two planned effects are
`https://www.googleapis.com/auth/gmail.compose` (Gmail drafts only; Jeff sends)
and `https://www.googleapis.com/auth/calendar.events`. Upstream's cumulative Gmail
permission mode may request broader scopes; do not accept those silently. Review
the effective grant with Jeff before any write-mode launch.

Execution journals `uncertain` durably before calling upstream. Errors, lost
responses or crashes never trigger an automatic second send/create. A successful
response records `submitted`, not delivered, with a receipt digest. Completed
and uncertain attempts cannot be edited into retries. Reconcile uncertain state
through the provider before preparing a new action.

Tests use fake MCP responses, real SQLite restart/replay and the same facade.
They cover sourced reads, exact drafts, stale recipient/body/time approval,
missing consent, expired ownership, conversation isolation, uncertainty and
duplicate prevention. Local tests and real-account acceptance are distinct:
daily brief/document access for Jeff remain blocked on OAuth. The runtime's
existing consent cards and provider router are not present on repository main;
their adapter wiring is pending an integration baseline. No live services or
Andrea files were changed.

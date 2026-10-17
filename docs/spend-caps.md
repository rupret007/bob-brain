# Per-model monthly caps and alerts

`SpendCap` uses SQLite transactions to reserve the maximum possible billable
cost BEFORE a provider request. Units are integer USD microdollars; one dollar
is 1,000,000 units. Model caps are explicit trusted configuration, with no default
funding or automatic increase. Unknown models fail closed. The billing month is
the request's admission month in America/Chicago. Reservations and settlement
receipts survive restart; an uncertain response retains its full reservation.

Keep the existing conductor/global hard budget and require BOTH gates before
dispatch. This supplements that policy and grants no money by itself. Provider
adapters must reserve a verified upper bound using current model prices and hard
token limits; if no bound exists, do not dispatch. Settle from provider usage,
never from a model's estimate. A zero settlement is allowed only after proof that
no billable request occurred. A receipt cannot be rewritten to reclaim budget.

80%, 95%, 100% and blocked-attempt alerts are durable local events, deduplicated
per model/month/threshold. Surface them in the all-bot status view. No email,
text, top-up or plan change is sent automatically. Existing spend must be imported
as settled receipts BEFORE activating a cap midway through a month. Unreconciled
historical usage blocks activation.

Tests exercise simultaneous reservations in one test process, model isolation,
restart/uncertainty, duplicate admission, immutable settlement, Chicago month
rollover and alert thresholds. Runtime provider hooks and actual cap amounts
remain setup work; no live spending policy was changed.

## Provider quota guard (ai-capacity)

Before admitting a reservation, `provider_quota_check` consults the latest
`ai-capacity/v1` snapshot for **measured** providers only (`codex`, `minimax`).
It **blocks** dispatch when the snapshot is missing, marked `snapshot_stale`, lacks
a matching row, has unknown `remaining_pct`, or reports non-finite or out-of-range
remaining (0–100), or remaining below 5%. **Unmeasured** providers (`claude`,
`gemini`, `xai`, `cursor`) are listed in the hardcoded `UNMEASURED_QUOTA_PROVIDERS`
constant in `webbob/spend_cap.py`; the quota guard is skipped for them (capacity
rows for those providers are never trusted for allow/deny). Any model that maps
to neither list fails closed. Unmeasured models still require a successful monthly
cap reservation; only the quota gate is exempt.

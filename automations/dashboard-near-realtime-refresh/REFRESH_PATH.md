# Dashboard near-realtime refresh — path (never-run bootstrap)

Automation id dir: `automations/dashboard-near-realtime-refresh/`
Cron (enabled): `*/15 8-22 * * 1-5` America/Chicago weekday window
`lastRunAt`: null as of 2026-08-22 ~9:15 PM CT — first live run not yet fired.

## Canonical command (push to Pages)

```bash
cd /workspace/bob-ops-dashboard   # or fresh: gh repo clone rupret007/bob-ops-dashboard
./refresh.sh --push               # rebuild index.html + status.json, commit+push main
```

Live Pages: https://rupret007.github.io/bob-ops-dashboard/

## Local-only (no push)

```bash
cd /workspace/bob-ops-dashboard
./probe-agents-status.sh > agents-status.json   # optional Mac/agent strip; skip if no Mac probe
./refresh.sh                                    # write index.html + status.json only
```

## Prefer skip when fresh

If Actions `refresh` or Pages deploy succeeded within ~10 minutes and `status.json` `generated_at` is fresh, stay quiet — do not duplicate `--push`.

## Constraints

- No secrets / CSOne / customer rows on public page
- AdoptIQ / TACTrack high-level only
- Do not start Cloud Agents for this routine

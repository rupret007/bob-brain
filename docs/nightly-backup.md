# Nightly accepted memory and configuration backup

Use the existing single scheduler and the report's APScheduler 3.x cron trigger
for 03:00 America/Chicago. `config/backup-job.json` is deliberately inactive until
the private destination, trusted export adapter and restore rehearsal exist.
No launchd service or live schedule is changed. Coalesce downtime to one latest
missed nightly occurrence; use the local date as its stable occurrence key.

`snapshot` accepts the P2 accepted-facts projection and exactly four nonsecret
configuration fields. It never walks directories or copies raw databases,
`keys.env`, dotenv files, OAuth tokens, sessions, private texts, raw voice or
conversation-specific consent. Sources must come through trusted accepted-fact
classification; do not classify arbitrary text as accepted to bypass filtering.
Sensitive markers conservatively reject the entire snapshot before any file is
written. This does not magically identify arbitrary unlabeled secrets: audited
source classification and narrow nonsecret projections are the primary boundary.

Snapshots contain a content digest and are written with mode 0600 using fsync
and a no-clobber publication. Store them in a private owner-only directory.
Duplicate occurrences cannot replace an existing backup. `read_snapshot` checks
the schema, privacy boundary and digest before returning restore candidates.
Restoration must use the trusted acceptance importer with revision reconciliation;
never overwrite live memory or revive forgotten facts automatically.

Tests rehearse round-trip restoration, tamper detection, duplicate-night
protection and rejection of secret/private source fixtures before filesystem
writes. No real secret file is read. No backup retention deletion is automated.
Schedule activation and a rehearsal using the selected release's actual accepted
export remain pending; do not claim a working nightly job from this component.

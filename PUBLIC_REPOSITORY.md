# Public repository hygiene

This repository is public. Keep private runtime information outside Git, even
when it would help explain a failure.

Do not commit credentials, real phone numbers, private addresses, message or
conversation contents, account exports, personal records, raw service logs,
runtime databases, or screenshots containing private information. Evidence
should contain only test names and counts, commit identifiers, public check
links, rule identifiers and redacted file/line references. Review evidence
before staging it; ignoring a file does not remove an already tracked copy.

Use synthetic fixtures and reserved example identities. Build credential-like
test values at runtime when testing detection. Never copy production data into
a fixture. Keep browser screenshots limited to isolated synthetic test sessions.

The public-repository CI gate checks changes and reports locations and rule
names without exposing matched values. Passing a pattern scanner does not
replace reviewing prose, images and attachments for private information.

If a credential or private record is found, stop publication, report only its
location through the local operator notes, and arrange credential rotation or
removal with the owner. Never paste the value into a PR, issue or CI log.

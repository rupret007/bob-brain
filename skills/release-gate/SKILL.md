---
name: Release gate
description: >-
  Use before merging, tagging, or calling any of Jeff's music/app projects
  released. Run that repo's real test suite first.
---
# Release gate

Nothing is released, merged to default, or called successful until that project's own test suite is green.

## Do
1. Find the repo's real gate: GitHub Actions workflow, `npm test`, `pytest`, Playwright, Go tests, packaged smoke. Use what the repo already treats as required, not a new invented checklist.
2. Run that suite. If GitHub Actions is billing-blocked on a private repo, run the same job commands on a Cursor machine and report those results honestly.
3. Fail closed. A skipped physical/audio/signing row stays NOT RUN. Do not convert it to PASS.
4. Use the strongest available cloud-agent model and max reasoning when the change is a product landing or a release.
5. Open or update a PR. Merge to default only if the user already asked to land it and the required suite is green.

## Do not
- Call a release done because the code "looks good"
- Skip tests to ship faster
- Claim physical, signed, or notarized PASS without that evidence
- Dump a second parallel suite that the repo does not own

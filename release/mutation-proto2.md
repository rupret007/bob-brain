# Protocol-2 mutation checks — 2026-10-16

Each mutation was applied separately to `webchat/texting.py`. Both commands
below detected every mutation with assertion failures (exit 1). The original
source was restored byte-for-byte after each mutation and verified by SHA-256.

| Mutation | Unit tests | Real-pin probe |
| --- | --- | --- |
| Accept any protocol (`return True`) | Killed | Unknown health protocol accepted |
| Drop the exact integer type check | Killed | Unknown health protocol accepted |
| Add protocol 3 to the allowlist | Killed | Unknown health protocol accepted |
| Skip draft approval response shape validation | Killed | Malformed approval response accepted |

```sh
PYTHONPATH=webchat python3 -m unittest test_texting.AndreaProtocolTests
PATH=/opt/homebrew/opt/node@22/bin:$PATH python3 release/bridge_probe.py \
  --andrea ../andrea-webbob-consent1015-1017 --output /tmp/webbob-proto2-probe.json
```

The current probe verifies Andrea pin `6f1030f9d1b8a8c973ccd3ef4c5cf148669179d1`
and its compiled artifact hash. It first runs the unmodified worker and verifies
disabled owner delivery. For the positive path, a temporary copy of that worker
installs Andrea's `OwnerChallengeDelivery` test seam; only Andrea mints the
approval, delivered to a private test owner inbox independently of HTTP.
Failed owner delivery, missing/forged approvals and legacy confirmation fields
are rejected. The pinned checkout and compiled modules are never edited.

The initial full run encountered a missing Playwright browser and one existing
optional browser skip. Installed the matching Chromium/WebKit runtimes and set
`BOB_PLAYWRIGHT_MODULE` to the existing shared package for the final run;
no tests were removed, weakened or disabled.

Historical verification (before the requestDigest binding changes; not qualification of the current pin): `python3 -m unittest discover -s webchat` passed all 3,165
tests in 283.473 seconds with zero skips. The 15 focused protocol/legacy client
tests also passed. The real-pin probe passed its 49 injected negative cases,
approval rejection checks, and one synthetic send with receipt recovery;
zero real texts or worker dispatches. Node 22 was first on `PATH`, with
`BOB_PLAYWRIGHT_MODULE` pointing to the shared `conductor/webchat/node_modules/playwright`.

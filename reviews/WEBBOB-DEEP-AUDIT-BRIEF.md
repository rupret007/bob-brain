# Web Bob deep audit brief (for council, 2026-09-27)

## Independent findings (measured tonight)

1. **Prior self-scores overstated failover live proof**: `live_failover.py` failed against production server because `BOB_WEBCHAT_DRILLS=1` was not set on the running process; `.drill.json` injections were ignored. Fixed: `X-Bob-Webchat-Drills` header + preflight in `live_failover.py`; `start.py` passes env into screen.
2. **Autopilot spawned overlapping Cursor agents**: hardcoded `n=6`, 90s sleep without waiting for screen completion → duplicate R6/R7 sessions. Fixed: derive next round from RESULT files; `wait_builders` after each round.
3. **Startup log leaked auth file path** as `password: /path/.password` in `logs/webchat-server.log` (not the secret, but poor hygiene). Fixed: generic startup line.
4. **Playwright iPhone smoke** used `waitForFunction` strings blocked by CSP `script-src 'self'`. Fixed: locator-based waits.
5. **Multiple detached `svc-webchat` screen sessions** possible; `start.py` idempotent health check can leave wrong instance up. Operational risk: document kill `screen -S svc-webchat -X quit` before forced restart.
6. **10-message drill**: PASS p50 **1.314s** (slower than R6 claimed 0.88s).
7. **Handback drill**: PASS ×2.
8. **Tailscale**: serve proxies `https://jeffs-mac-mini.tail758ab4.ts.net` → `127.0.0.1:8787`; login sets `Secure` cookie on ts.net Host (unit test).
9. **launchd** `com.jeff.bob-webchat` installed; LastExitStatus 0; StartInterval 60s.
10. **Conductor parity**: council/job flows are confirm-first in unit tests; full council still runs on mini via queued job, not inline in chat API.

## Ranked fixes (proposed)

1. **P0** — Failover drill preflight + drills header (done).
2. **P0** — Autopilot single-builder guard (done).
3. **P1** — Startup log redaction (done).
4. **P1** — Playwright CSP-safe smoke + layout metrics (done).
5. **P2** — Structured `events` on public live_ops (done in working tree).
6. **P2** — `compact_digest` on every provider turn for handoff (done in working tree).
7. **P3** — Single canonical screen session for webchat restart helper script.
8. **P3** — Inline council from phone without mini job queue.

Vote: which ranked items should ship tonight vs defer?

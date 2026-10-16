# Single all-bot status view

`render_status` produces a standalone phone-readable HTML table for Grok Bot,
Web Bob, Andrea and Karen. Feed it explicit heartbeat observations from the
existing service/coord observers; do not infer health from process names or old
QA files. Missing, malformed, future and stale observations are unknown, not up.
Health, pending count and review status remain distinct; a PASS does not authorize
a release. Only fixed labels and selected scalar state are rendered, with no
private logs, inbox bodies, prompts, credentials or remote assets.

Mount the renderer in the existing authenticated status/front-door endpoint.
This branch starts no listener and changes no daemon. Runtime observer/route
wiring remains pending because main contains only Bob's backup. Tests verify all
four rows, stale/unknown health, actual down state and privacy-field exclusion.

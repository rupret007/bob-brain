# Grok Bot fallback notice

Call `fallback_notice` with observed Web Bob and Mini health in the external
front-door/status page, so a stopped Web Bob cannot hide its own fallback notice.
Fresh explicit down states and unknown/stale states have distinct copy. The
notice suggests Grok Bot conditionally; it does not assert Grok availability,
automatically switch accounts, send messages, or forward conversation data.

This branch supplies the render contract and tests for both failures, recovery,
missing observations, stale/future timestamps and invalid numbers. Runtime UI
wiring needs the selected Web Bob baseline, absent from repository main.

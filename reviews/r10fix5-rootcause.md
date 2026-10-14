# r10fix5: do not invent completed snapshots/receipts on unavailable paths

gate_avg at `26071a0` (r10fix4) still failed Codex truth on
`provider_unavailable` (exposed 0/2). r64's blocker was T4 claiming a
"previously prepared evidence snapshot" that earlier turns only proposed.
r63 also invented save receipts, hold IDs, and live route claims.

r10fix4 kept server-owned `lifecycle stage` / `receipt` wording through
`Chat.save`. That was necessary but not sufficient: `resource_decision`
still accepted model reasoning that promoted a proposed preparation step
into a completed receipt. Resource advice never executes
(`execution_started` is always false), so those completions are fabricated.

Repair: reject asserted completed-preparation, save-receipt, hold-ID, and
live-route claims in `safe_reasoning`, and fail closed on unavailable
projections in `feasible_reasoning`. Server availability facts and honest
"proposed / no receipt recorded" wording remain. No existing assertion
changed.

# Web Bob Round 15 — design note (research-first)

**Borrow**
- R14 council ranked fixes: passive `load_live_ops()` (no subprocess on read), truthful stale labels in Jobs, preserve `request_id` on provider replies for live call correlation.
- Detailed live dashboard (Jeff 02:03): per-job elapsed + stall in Jobs dl grid; scores compact on Jobs tab (R14 wiring, R15 polish).
- Apple HIG / Grok Bot chat-first layout (Jeff 02:18): bottom tab bar unchanged; one-tap chips submit round/council/status (R14).

**Reject**
- MiniMax music API / new signups (Jeff 02:00).
- Spawning `dashboard_cycle()` from phone panel reads (council R14 vote).
- Grok as worker.

**Why**
- Lowest R14 scores: self-improve loop (9.32), voice (9.58), conductor parity (9.64), enhancement 1 (9.62).
- R15 targets passive dashboard architecture + call `request_id` hardening + self-improve start-line regression.

**Sources:** `WEBCHAT-READY-R14-RESULT.md`, `webchat-ready-r14-council/20260927-042720-037671.md`, `ALIGNMENT-DESIGN.md`, MDN Web Speech API.

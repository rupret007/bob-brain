# Web Bob Round 17 — design note (research-first)

**Borrow**
- Jeff TOP: bidirectional handback drills ×2 with isolated fixture (`live_handback_drill.py`, `drill_fixture.py`).
- ADDED 02:03 detailed live dashboard: show tracked + live jobs in Jobs dl grid; `stall_plain` + `display_state` on every card.
- ADDED 02:51 quiet hours 11 PM–7 AM CT for read-aloud (live call unchanged).
- Self-improve bootstrap one-liner in panel API (`bootstrap_command`) so Jeff can load launchd without reading paths.
- ALIGNMENT-DESIGN.md event log + BOB-CATCHUP (unchanged contract).

**Reject**
- MiniMax music API / signups (Jeff 02:00).
- Grok as worker.
- Restart webchat mid-reply (03:40 gentle restarts — single restart end of round only).

**Why**
- Lowest R16 scores: self-improve (9.44), voice (9.64), mobile formatting / Jobs plain English (9.66).
- R17 targets dashboard completeness (non-screen jobs in ops detail), self-improve bootstrap clarity, call latency hint, quiet-hours read-aloud guard, refrain-only music coach.

**Sources:** `WEBCHAT-READY.md` ADDED 02:03/02:51/04:18, `WEBCHAT-READY-R16-RESULT.md`, Apple HIG tab bar, MDN Intl timeZone.

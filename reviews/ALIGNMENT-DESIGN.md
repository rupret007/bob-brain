# Bob ↔ Web Bob alignment design (Round 9)

**Council vote (R9):** adopt **(a) `events.jsonl` + SSE in Web Bob** with **STATE.json** as structured SSoT; reject GitHub sync bus for live chat (latency/cost), Grok webhook wake (forbidden), and Bob polling.

## Options compared

| Option | Borrow | Reject | Why |
|--------|--------|--------|-----|
| (a) `conductor/state/events.jsonl` + SSE | Append-only audit, fsync, seq cursor | Full event-sourcing engine | Bob wakes on BOB-CATCHUP; Web Bob stays live |
| (b) Private GitHub repo as bus | Immutable history | Per-message fetch cost for Bob | Bob usage must stay near zero until ~10/2 |
| (c) Grok webhook wake | Push on blockers | Grok forbidden | Hard rule |
| (d) BOB-CATCHUP only | One-read handback | Sub-5s phone freshness | Supplement, not replace live bus |

## What we built (R9)

- `alignment_events.py` — locked append, monotonic `seq`, rotation at 2000 lines.
- Writers: `record_webchat_turn`, `append_inbox`, `append_turn` (handback).
- Readers: `/api/alignment/events`, `/api/alignment/stream` (SSE), Jobs panel `alignment_events` slice.
- Pickup: `HANDBACK-SUMMARY` **Latest pickup** from ledger `open_asks` + live jobs (not log regex for “Open”).
- Projections unchanged: `STATE.json` → NOW / INBOX / BOB-CATCHUP under `_mutate` flock.

## Sources

- [Temporal event history](https://docs.temporal.io/workflows) — append log + derived views
- [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) — checkpoint + projections
- Jeff `WEBCHAT-READY.md` ADDED 03:04 — near-real-time alignment requirement

## Remaining (effort)

- **M:** Event cursor ack for catch-up (don’t re-list consumed turns).
- **M:** Web push when `kind=blocker` events arrive.
- **S:** Multiprocess barrier test for `events.jsonl` + ledger interleave.

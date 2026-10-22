# Web Bob Round 13 — design note (research-first)

**Borrow**
- Apple HIG tab bar + grouped Settings lists (iOS-native ops detail on Models tab).
- ALIGNMENT-DESIGN `events.jsonl` + paginated catch-up with explicit `truncated` / `has_more` (Codex R12 council).
- Grok Bot chat bar order (mic in pill, waveform call) — unchanged; R13 hardens call utterance queue.

**Reject**
- MiniMax music API / new signups (Jeff 02:00).
- Grok as worker.
- Restarting webchat mid-reply per deploy (03:40) — still defer batch restart policy; single safe restart this round only.

**Why**
- Lowest R12 scores: self-improve clarity, voice serialization, music coach breadth, catch-up loss at >240 events.
- Detailed live dashboard belongs on Models tab as a dl grid (plain English), not above chat.

**Sources:** `conductor/reviews/ALIGNMENT-DESIGN.md`, `WEBCHAT-READY-R12-RESULT.md`, Apple HIG Tab Bars, MDN Web Speech API.

# Web Bob Round 14 — design note (research-first)

**Borrow**
- R8/R13 detailed live dashboard contract (`running_jobs[]` log tail, scores, roles, MiniMax cap) — extend Jobs tab dl grid with per-job snippets + compact scores (Jeff 02:03).
- One-tap quick chips that submit (not only prefill) for status / round / council — pairs with existing approve cards (Jeff 02:19, 04:18).
- Grok Bot call barge-in: cancel TTS on interim speech (MDN `SpeechRecognition` interimResults).
- Self-improve loop visibility: streak of OK ticks + `loop_ready` flag for Settings/Jobs (Jeff 00:42).

**Reject**
- MiniMax music API / signups (Jeff 02:00).
- Grok as worker.
- Auto-confirm jobs without approve card (safety).

**Why**
- Lowest R13 scores: self-improve loop (9.28), run jobs from chat (9.6), conductor parity (9.58), voice (9.52), music (9.65).
- Jobs tab must mirror Models dashboard detail, not only summary rows.

**Sources:** `WEBCHAT-READY-R13-RESULT.md`, `WEBCHAT-READY-R8-RESULT.md`, Apple HIG tab bar, MDN Web Speech API, `ALIGNMENT-DESIGN.md`.

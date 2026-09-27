# Web Bob R12 design note (research-first)

**Date:** 2026-09-27 CT · **Council:** R12 critique after build · **No Grok.**

## Borrow

| Source | Take | Reject |
|--------|------|--------|
| [Apple HIG Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Persistent bottom tabs; chat-first main view | Pop-over sheets for primary nav (R10–R11 Jeff feedback) |
| [Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API) | Live call v1: continuous recognition + `speechSynthesis` barge-in on iPhone Safari | Full WebRTC streaming STT until whisper stream is wired on mini |
| R9 isolated `drill-fixtures/` + overlay | Prod fingerprint unchanged; handback ×2 drill | Mutating prod `events.jsonl` for ready-drill phrases |
| `events.jsonl` + paginated catch-up (ALIGNMENT-DESIGN) | Bob wake reads all pages since ack | Bob polling |

## R12 build focus (lowest R11 scores)

1. **Architecture / safety:** Skip prod alignment events for ready-drill noise; paginated catch-up events.
2. **Voice:** Grok-style waveform live-call button + dialog (listen/speak/barge-in).
3. **Music:** Structure/tempo coach paths (no MiniMax music API).
4. **Live dashboard:** Models tab plain-English ops line (freshness, spend, roles, scores); scores table picks highest READY round number.

## Prove

- Handback drill `WEBCHAT_HANDBACK_TAG=r12` ×2 runs ×2.
- `live_ready_drill.py` + unit tests.
- Playwright 390×844 / 430×932 in `webchat/evidence/iphone-r12/`.

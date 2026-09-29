# Web Bob Round 23 — research-first design note (on R17)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R17 final `5e8fa8b` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| Apple HIG (tab bars, materials) | Frosted bottom tab bar (already); hide chrome that competes with chat | Pop-up sheet for main nav | Jeff 02:30 — real tab bar only |
| ChatGPT / Claude iOS | Chat ≥75% height; typing avatar row; per-message actions via long-press | Raw STATUS dumps in Chat | Jeff 02:11 / 02:18 |
| Grok Bot ref (`grokbot-ref-chatbar-0346.png`) | Pill composer, mic + waveform in pill, slim header pill | Pixel-perfect clone of Grok branding | North star feel, Bob identity |
| R23 council hold notes | `scores_measured_at` ≠ snapshot `generated_at`; queue `position` on Jobs | Builder self-grade | Independent dashboard truth |
| Jeff 02:00 music | Lyrics/meter/rhyme/cadence coaches ($0); Logic MCP confirm-first | MiniMax music API / signups | 410 not entitled |
| LangGraph / handoff patterns (prior rounds) | Isolated handback drills + `events.jsonl` | Bob polling while usage-capped | Bob reads on wake only |

## R23 build focus (lowest R17 scores first)

1. **iPhone design (9.98 → ≥9):** Cleaner chat — hide per-message Copy on phone (long-press menu stays); subtle bubble depth; restore **queued** Jobs cards with plain **Next up** / **#N in queue** (scheduler `position`).
2. **Safety / dashboard truth (9.97):** Jobs + Models show **Scores measured** from `scores_measured_at` (latest RESULT mtime), never conflate with ops snapshot refresh time.
3. **Failover both ways (TOP):** `WEBCHAT_HANDBACK_TAG=r23` live drill **×2** + `e2e_live.py --isolated`.
4. **Live dashboard (02:03):** Document full pipeline in RESULT; queued backlog visible on Jobs tab again.
5. **Council:** Gemini + MiniMax + Claude short critique on diff; vote to ship after gates.

## Sources

`WEBCHAT-READY.md` ADDED 02:03, 02:11–02:30, 02:44–02:45; `WEBCHAT-READY-R17-RESULT.md`; Apple HIG; web.dev mobile typography; `ALIGNMENT-DESIGN.md`.

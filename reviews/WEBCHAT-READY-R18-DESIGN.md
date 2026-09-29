# Web Bob Round 18 — design note (research-first, on R27 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R27 final `4b6fb34` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| Apple HIG (tab bars, sheets) | Persistent bottom tab bar; modals dim + blur behind; **Settings** label with safe truncation | Pop-up sheet with Done for primary nav | Jeff 02:30 — tabs must stay visible |
| ChatGPT / Claude iOS | Chat ≥75% viewport; slim header; chips as one scroll row; assistant bubble contrast | Raw STATUS markdown in chat | Jeff 02:11 iPhone-first |
| Grok Bot ref (`grokbot-ref-chatbar-0346.png`) | Pill composer, mic + call waveform, grey user bubbles | Grok as worker | North star UX only |
| R27 scorecard (weakest) | **Speed** 9.82, **Self-improve** 9.86, **Music** 9.91 | MiniMax music API | Measured gaps; Jeff 02:00 |
| ADDED 02:03 dashboard | MiniMax **% of $59** + headroom on Jobs/Models ops | Guessed spend | Real ledger numbers only |
| ALIGNMENT / handback | `WEBCHAT_HANDBACK_TAG=r18` ×2 isolated | Prod STATE mutation | Zero lost context both ways |
| Council R27 pattern | Hold → gates → RESULT → ship draft | Self-grade without Playwright | Fail-closed |

## R18 build focus (lowest R27 scores first, iPhone-first first)

1. **iPhone design (TOP):** Rename tab **Settings** (fix cut-off); hide header Jobs shortcut on phone (tab bar owns it); collapsible quick chips for more message height; stronger modal backdrop + no washed-out chat behind dialogs; assistant bubble contrast; larger lyrics editor; council screenshot pass `iphone-r18`.
2. **Speed (9.82):** Short TTL panel cache (fresh `in_flight` / deploy restart each hit); slightly tighter chat poll while a reply is in flight.
3. **Self-improve (9.86):** Setup shows **one-line install CTA** when launchd unloaded + gap-to-9 beside focus (inherits R27, clearer copy).
4. **Music (9.91):** **Plagal cadence (IV→I)** coach line on $0 progression scan; parity eval +1.
5. **Live dashboard:** Ops rows **MiniMax % used** and **headroom** from `minimax_spend`.
6. **Proof:** handback ×2, ts.net ready drill, 35+ parity, council (Gemini/MiniMax/Claude), restart 8787.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

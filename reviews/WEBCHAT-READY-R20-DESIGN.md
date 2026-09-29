# Web Bob Round 20 — design note (research-first, on R35)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R35 final `d025af6` · **No Grok.**

## Research pass (iPhone-first, then gates)

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Fixed bottom tabs, icon + short label, 44pt targets | Pop-up “Done” sheet for primary nav | Jeff 02:18/02:30 — chat must own ~75%+ height |
| [ChatGPT iOS](https://openai.com/chatgpt) / Claude iOS patterns | Chat-first, slim header pill, composer pinned above keyboard | Raw STATUS markdown above messages | Jeff saw file dumps crowding chat |
| Grok Bot ref (`reviews/grokbot-ref-chatbar-0346.png`) | Mic inside pill + separate call control | Pixel-perfect clone without Web Bob extras | North star feel; we keep Jobs/Models tabs |
| R35 scorecard (lowest) | **Enhancement 4 voice 9.96**, **Safety 9.96**, **iPhone 9.97** | MiniMax music API | 410 not entitled (Jeff 02:00) |
| R35 structural #5 | Handback drill **6×2s** prod fingerprint retry | Blocking prod ledger during drills | Reduces race with autopilot/chat |
| ADDED 02:03 dashboard | Keep `enrich_live_ops_bundle` + Unknown ops row (R35) | Second dashboard writer | Single pipeline to Pages + `/api/panel` |
| ALIGNMENT-DESIGN (events.jsonl + catch-up) | Continue isolated drills + `events_ok` | Bob polling | Bob usage cap to ~10/2 |

## R20 build focus (order)

1. **iPhone design (TOP):** Settings tab label (not “Prefs”), higher assistant bubble contrast, lighter modal dim, live-call transcript readability.
2. **Failover (TOP):** `WEBCHAT_HANDBACK_TAG=r20` handback **×2**, `prod_unchanged: true`.
3. **Dashboard (02:03):** Document inherited R35 live ops contract in RESULT; no duplicate writers.
4. **Music ($0):** ABABCB / song-form coach + parity case.
5. **Council:** Gemini + MiniMax + Claude via `council.py`; vote on disagreements.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

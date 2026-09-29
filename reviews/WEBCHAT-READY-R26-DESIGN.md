# Web Bob Round 26 — design note (research-first, on R25 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R25 final `9d4d27f` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R25 weakest rows | Self-improve + voice + mobile formatting | New music API | 9.93/9.93/9.94 first |
| Jeff 02:00 music | Subdominant (IV) on $0 progression scan | MiniMax music API | 410 not entitled |
| ADDED 02:03 dashboard | Commit message on Jobs ops job rows | Raw log paths | Plain English on phone |
| R25 architecture #5 | Handback `prod_unchanged` retry (3×, 1.5s) | Ignore race | Rare STATE sync flake |
| ALIGNMENT handback | `WEBCHAT_HANDBACK_TAG=r26` ×2 isolated drills | Prod mutation | Zero lost context |
| Council R25 | Ship after tests + drills + parity | Self-grade only | Independent grader |

## R26 build focus (lowest R25 scores first)

1. **Self-improve (9.93):** `scores_weakest_focus` from latest READY RESULT + Settings detail row; loop-ready plain status names next focus.
2. **Voice (9.93):** Stronger voice-transcript contrast (border, weight) on voice bubbles.
3. **Enhancement 1 — mobile (9.94):** Assistant `md-link` parity with user bubbles (word-break, underline-offset).
4. **Live dashboard:** Ops job snippets include last commit **message** after SHA.
5. **Music (9.98 → ≥9.99):** Subdominant (IV) line on progression scan ($0).
6. **Architecture:** Handback drill prod fingerprint retry; parity eval +1 subdominant case.
7. **Failover proof:** handback drill ×2 + ts.net ready drill; Bob parity eval 31/31.

## Council

Gemini + MiniMax + Claude (short) via `council.py`; synthesizer vote; no Grok.

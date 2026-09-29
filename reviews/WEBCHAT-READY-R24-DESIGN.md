# Web Bob Round 24 — design note (research-first, on R13 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R13 final `021c527` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [HTTP caching patterns](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching) | 2s TTL for identical status reads | Long-lived stale status | Jeff back-to-back status chips on phone |
| Apple HIG / Grok Bot ref | Ops freshness separate from score measurement | One timestamp for everything | R23 council hold |
| Jeff 02:00 music | Relative-minor hint on chord scan ($0) | MiniMax music API | 410 not entitled |
| ALIGNMENT `events.jsonl` | Handback drill isolated fixtures | Prod STATE mutation | 03:17 P0 |
| Council R13 hold | Exact `drill open item ({tag})` in catch-up | Generic "open ask" pass | Zero lost context |

## R24 build focus (lowest R13 scores first)

1. **Speed (9.86):** `_status_snapshot()` 2s TTL — one STATE+NOW read per burst of status asks.
2. **Self-improve (9.92):** Settings always shows launchd schedule + verified ship detail when loop is ready.
3. **Enhancement 1 mobile (9.93):** Link styling in user bubbles (`md-link`, underline-offset, word-break).
4. **Live dashboard (02:03):** Models/Jobs ops row **Ops snapshot** age from `generated_at` (distinct from scores measured-at).
5. **Music (9.96 → ≥9.97):** Relative-minor line on progression scan (C → Am vi).
6. **Failover proof:** `WEBCHAT_HANDBACK_TAG=r24` live drill ×2 + ts.net ready drill; `prod_unchanged: true`.

## Council

Gemini + MiniMax + Claude (short) on R24 diff; synthesizer vote; no Grok.

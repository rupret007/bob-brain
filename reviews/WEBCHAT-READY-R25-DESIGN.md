# Web Bob Round 25 — design note (research-first, on R24 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R24 final `0ca013d` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R24 architecture #5 | Invalidate status cache on ledger mutate | TTL-only after handback | Stale cheap-status after open asks |
| Jeff 02:00 music | Dominant (V) + relative minor (vi) on $0 scan | MiniMax music API | 410 not entitled |
| ADDED 02:03 dashboard | `queue_next_preview` + `tracked_job_count` on ops panel | Raw INDEX.md in UI | Plain English for phone |
| ALIGNMENT handback | `WEBCHAT_HANDBACK_TAG=r25` ×2 isolated drills | Prod STATE mutation | Zero lost context |
| Council R24 | Ship after invalidation test + live evidence | Self-grade without drills | Independent grader pattern |

## R25 build focus (lowest R24 scores first)

1. **Conductor parity (9.94):** Models/Jobs ops detail shows next queued goal + tracked job count from live ops bundle.
2. **Enhancement 2 — jobs from chat (9.94):** `start a job for me` maps to conductor follow-up queue (same as do-more).
3. **Self-improve (9.93):** unchanged logic; schedule stays in Settings headline (R24).
4. **Music (9.97 → ≥9.98):** Dominant (V) line on progression scan alongside vi.
5. **Architecture:** `invalidate_status_snapshot()` on every `_mutate`; regression test after `add_open_ask`.
6. **Failover proof:** handback drill ×2 + ts.net ready drill; Bob parity eval 30/30.

## Council

Gemini + MiniMax + Claude (short) via `council.py`; synthesizer vote; no Grok.

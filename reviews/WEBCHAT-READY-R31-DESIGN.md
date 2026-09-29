# Web Bob Round 31 — design note (research-first, on R30 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R30 final `72e490b` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R30 weakest rows | Enhancement 2 **9.94**, Enhancement 4 voice **9.93** | MiniMax music API | Jeff 02:00 |
| ADDED 02:03 dashboard | `dashboard_plain` must include scheduler queue + ops snapshot on Pages and Jobs | Building plain rows before queue attach | Queue row was missing on phone/Pages |
| Mobile voice UX | Settings toggle for auto read-aloud; shared speak helper | Cloud TTS signup | Local voices first |
| Enhancement 2 | Confirm cards show goal text; queue row on dashboard | Read-only conductor | Jeff 04:18 |
| Music ($0) | Bridge coach parity case | Paid gen | Keys Jeff has |
| Failover | `WEBCHAT_HANDBACK_TAG=r31` ×2 isolated | Prod mutation | Zero lost context |

## R31 build focus (lowest R30 scores first)

1. **Enhancement 2 (9.94):** Job confirm cards surface the goal; scheduler queue appears in `dashboard_plain` after enrich (queue attach before plain build).
2. **Voice (9.93):** Settings **Read new replies aloud** toggle (localStorage); respects quiet hours; 🔊 reuses shared speak path.
3. **Dashboard (02:03 detail):** **Ops snapshot** row in `dashboard_plain`; document full field table in RESULT.
4. **Music (9.96):** **Bridge coach** parity case ($0).
5. **Failover proof:** handback drill ×2 (`r31`) + ts.net ready drill.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

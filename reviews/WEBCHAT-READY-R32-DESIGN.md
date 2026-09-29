# Web Bob Round 32 — design note (research-first, on R31 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R31 final `78a4ab1` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R31 weakest rows | iPhone design **9.94**, voice **9.95**, self-improve **9.95** | MiniMax music API | Jeff 02:00 |
| R31 structural #5 | `dashboard_plain` **+N more** row + `dashboard_plain_omitted` on Pages | Silent truncation at 18 | Jeff cannot see dropped ops on phone |
| ADDED 02:03 dashboard | **Bob catch-up** row in plain grid (top 3 lines) | Raw handback on Jobs | Plain English only |
| Mobile voice UX | Settings **read-aloud speed** (device TTS) | Cloud TTS signup | Local voices |
| Music ($0) | **Intro + outro** coach parity (45 cases) | Paid gen | Keys Jeff has |
| Failover | `WEBCHAT_HANDBACK_TAG=r32` ×2 isolated | Prod mutation | Zero lost context |

## R32 build focus (lowest R31 scores first)

1. **iPhone design (9.94):** Dim chat behind modals; show full **18** plain dashboard rows on Jobs; overflow **More fields** row.
2. **Voice (9.95):** Read-aloud speed control in Settings; shared `speakRateValue()` for auto 🔊.
3. **Dashboard (02:03 detail):** `bob_catchup_preview` in `dashboard_plain`; document overflow contract in RESULT.
4. **Music (9.97):** Intro + outro coach eval cases ($0).
5. **Failover proof:** handback drill ×2 (`r32`) + ts.net ready drill.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

# Web Bob Round 30 — design note (research-first, on R29 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R29 final `5c2b964` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R29 weakest rows | Enhancement 1 **9.94**, Enhancement 2 **9.94**, Self-improve **9.93** | MiniMax music API | Jeff 02:00 |
| ADDED 02:03 dashboard | Deploy, in-flight, stalled, 3-line **Recent logs**, last commit in `dashboard_plain` | Raw filenames in chat | Jeff cannot see terminal |
| Mobile UX | Blockquote markdown, full-contrast bubbles; live ops stay on **Jobs** tab | In-chat status dumps | 02:18 layout |
| Conductor parity | Autopilot respects in-flight + builder lanes before “finished” | Syntax-only conductor tab | Jeff 02:30 |
| Music ($0) | Explicit **meter scan** phrase + parity case | Paid gen | Keys Jeff has |
| Handback | `WEBCHAT_HANDBACK_TAG=r30` ×2 isolated | Prod mutation | Zero lost context |

## R30 build focus (lowest R29 scores first)

1. **Enhancement 1 (9.94):** Markdown blockquotes; code-block order fix; assistant bubble contrast (chat ≥75% height preserved).
2. **Enhancement 2 / Self-improve (9.94 / 9.93):** Settings **chat_queue_hint**; **install_one_liner** on API when launchd unloaded.
3. **Dashboard (02:03 detail):** `dashboard_plain` rows for deploy, safe restart, in-flight, scores age, stalled, last commit, recent logs; panel re-enrich after in-flight known.
4. **Conductor parity (9.95):** Jobs autopilot string when replies in flight.
5. **Music (9.95):** `meter scan` explicit trigger; **42/42** parity.
6. **Failover proof:** handback drill ×2 (`r30`) + ts.net ready drill.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

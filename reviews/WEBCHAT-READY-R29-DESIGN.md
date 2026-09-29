# Web Bob Round 29 — design note (research-first, on R28 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R28 final `38e6aa4` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R28 weakest rows | Enhancement 2 **9.91**, Self-improve **9.91** | MiniMax music API | Jeff 02:00 — not entitled |
| ADDED 02:03 dashboard | `dashboard_plain[]` + Jobs tab grid + Pages | Raw log filenames | Jeff cannot see terminal |
| Mobile ops UX (Apple HIG) | Quick **Start job** chip, live-activity line above cards | Status dumps above chat | 02:18 layout |
| Music theory ($0) | **Half cadence** (ends on V) | Paid gen APIs | Keys Jeff has |
| ALIGNMENT handback | `WEBCHAT_HANDBACK_TAG=r29` ×2 isolated | Prod mutation | Zero lost context |
| Council R28 | Hold until RESULT + gates | Self-grade only | Fail-closed |

## R29 build focus (lowest R28 scores first)

1. **Enhancement 2 (9.91):** **Start job** quick chip; queued reply names the goal; `chat_queue_hint` when jobs row is weakest.
2. **Self-improve (9.91):** `chat_queue_hint` in API + Settings path (queue builder work without waiting for launchd).
3. **Dashboard (ADDED 02:03):** `dashboard_plain` in `enrich_live_ops_bundle` → Jobs tab + `public_live_ops` for Pages; **Live activity** line on Jobs header.
4. **Music (9.94):** Half cadence on $0 progression scan; parity **41/41**.
5. **Failover proof:** handback drill ×2 (`r29`) + ts.net ready drill; Web Bob **beats** Bob on expanded eval.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

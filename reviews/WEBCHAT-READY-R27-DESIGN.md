# Web Bob Round 27 — design note (research-first, on R17 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R17 final `db564cf` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R17 weakest rows | Self-improve 9.78, Music 9.86, Conductor 9.91 | MiniMax music API | Jeff 02:00 — 410 not entitled |
| ADDED 02:03 dashboard | Deploy SHA + safe-restart on Jobs/Models ops grid | Raw defer JSON | Plain English on phone |
| ALIGNMENT handback | `WEBCHAT_HANDBACK_TAG=r27` ×2 isolated | Prod mutation | Zero lost context both ways |
| Apple HIG tab bars | Ops detail in Models tab, not above chat | Status dumps in chat | Jeff 02:18 layout |
| Council R17 | Ship after gates + independent grader | Self-grade only | Fail-closed |

## R27 build focus (lowest R17 scores first)

1. **Self-improve (9.78):** `plain_status` names `scores_weakest_focus` even when launchd not loaded; Setup shows gap-to-9 + headroom.
2. **Music (9.86):** **Tonic (I)** line on $0 progression scan.
3. **Conductor / dashboard (9.91):** Jobs + Models ops detail rows for **Deploy version** and **Safe restart** from panel `deploy_head_sha` / `deploy_restart`.
4. **Failover proof:** handback drill ×2 + ts.net ready drill; Bob parity eval +1 tonic case.
5. **Inherited:** bidirectional handback, live ops enrich, iPhone tab layout, council on diff.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

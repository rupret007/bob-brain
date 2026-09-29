# Web Bob Round 19 — design note (research-first, iPhone TOP)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R32 final `e7d9f44` / HEAD pre-R19 · **No Grok.**

## Research pass (mobile AI chat + orchestration)

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Fixed bottom tabs, icon+short label, 44pt targets | Pop-up “Done” sheets for primary nav | Jeff 02:30 — tabs must stay visible |
| ChatGPT / Claude iOS (Jeff daily use) | Chat ≥75% viewport, composer pinned, extras in other tabs | Status markdown above thread | Jeff 02:18 layout decision |
| Grok Bot iPhone ref (`reviews/grokbot-ref-chatbar-0346.png`) | Slim header pill, mic inside pill, waveform call button right | Pixel-perfect Grok branding | Match feel, Bob identity |
| [PWA on iOS](https://web.dev/learn/pwa/installation/) | `viewport-fit=cover`, safe-area, `apple-mobile-web-app-capable` | Push without Jeff yes | Already in manifest |
| R32 weakest rows | iPhone **9.95**, voice **9.96**, self-improve **9.95** | MiniMax music API | Jeff 02:00 — not entitled |
| R32 structural #5 | **Second live job** row in `dashboard_plain` | Third+ jobs in plain grid | Busy mini visibility without dump |
| Failover patterns (handback ledger) | `WEBCHAT_HANDBACK_TAG=r19` isolated ×2 | Prod STATE mutation | Zero lost context |
| Voice UX research | `speakRateValue()` on **live call** TTS (same as 🔊) | Cloud streaming TTS signup | Local Safari voices only |

## R19 build focus (lowest R32 scores first)

1. **iPhone design:** Default **collapsed quick chips** on narrow viewports (more message area); tab **view transition**; assistant bubble contrast bump; Settings tab uses **Prefs** label + `aria-label="Settings"` so label is not clipped.
2. **Voice (9.96):** Live call replies respect Settings read-aloud speed (`speakRateValue()`).
3. **Dashboard (02:03):** **Also running** plain row when a second live screen job exists.
4. **Music ($0):** Pre-chorus coach parity case in eval.
5. **Failover:** handback drill ×2 (`r19`) + ts.net ready drill; Web Bob vs Bob parity maintained.

## Council

Gemini + MiniMax + Claude via `conductor/services/council.py`; synthesizer vote; no Grok.

# Web Bob Round 21 — research-first design note

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Base:** R14 `c04cbf4` · **No Grok.**

## Research pass (iPhone-first + alignment)

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Fixed bottom tabs (Chat/Jobs/Songs/Models/Settings); status only in other tabs; 44pt targets | Pop-up sheet with Done; status dumps above chat | Jeff 02:18–02:30 screenshots |
| [Apple HIG — Safe areas](https://developer.apple.com/design/human-interface-guidelines/layout) | `env(safe-area-inset-*)`, `100dvh`, composer pinned above tab bar | Raw markdown/file names in chat chrome | Phone primary device |
| [web.dev contrast](https://web.dev/articles/color-and-contrast-accessibility) | Provider hints, log tails, voice transcript at full text color | Faded assistant meta behind sheets | R14 voice 9.58 gap |
| ChatGPT / Claude iOS patterns (observed) | Chat ≥75% viewport; slim header pill; quick chips; typing indicator | Multi-panel dashboards in conversation | 02:11 north star |
| Grok Bot iPhone ref (`reviews/grokbot-ref-chatbar-0346.png`) | Mic inside pill + separate call waveform; floating identity pill | Copying Grok as a worker | 03:47 UX only — no Grok API |
| LangGraph / checkpoint handoff literature | Isolated `drill-fixtures/` + append-only handback; `events.jsonl` alignment | Prod STATE/HANDBACK during drills | P0 03:17 + ALIGNMENT-DESIGN |
| MiniMax music API | — | New endpoints (410) | Jeff 02:00 — LLM + notebook + Logic MCP only |
| Council fail-closed (R12–R14) | `latest_verified_ready_ship()` from PASS/FAIL table | Any latest RESULT SHA as “ship” | Self-improve 9.32 gap |

## R21 build focus (lowest R14 scores first)

1. **Self-improve loop (9.32):** Verified READY ship gate; Settings shows verified vs unverified RESULT SHA.
2. **Voice / mobile formatting (9.58 / 9.62):** Contrast on provider hints, job log tails, voice transcript CSS; tighter phone header/composer for chat height.
3. **Speed + live dashboard (9.74 / enhancement 3):** Jobs summary + ops detail show `generated_at`, `scores_weakest`; Models highlights weakest on lane refresh.
4. **iPhone design (9.86 → ≥9):** Chat-first layout metrics 390×844 / 430×932; weakest score card accent on Jobs/Models.
5. **Failover both ways (TOP):** `WEBCHAT_HANDBACK_TAG=r21` isolated drill ×2; live ts.net ready drill; zero prod fingerprint change.
6. **Music (9.70):** Unchanged — lyrics/chords via LLMs + notebook ($0).

## Council

Gemini + MiniMax + Claude (short) on R21 diff; synthesizer vote; no Grok.

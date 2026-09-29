# Web Bob Round 16 — design note (research-first, on R13 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R13 final `699cd26` · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Tappable rows with 44pt targets; Jobs tab for ops detail | Duplicating every job in the plain grid | Jeff 02:18 chat-first; R13 18-row cap |
| [Material — drill-down navigation](https://m3.material.io/foundations/interaction/gestures) | Summary → detail jump with highlight | New routes or modals per job | Matches queue “View in Jobs” pattern in `app.js` |
| R13 RESULT structural #5 | **`focus_live_job` actions** on Top / Also / More plain rows | MiniMax snippet list in grid | Council R13 count+stalled vote |
| `ALIGNMENT-DESIGN.md` | Isolated `WEBCHAT_HANDBACK_TAG=r16` ×2; `events.jsonl` | Prod ledger mutation in drills | P0 03:17 |
| Music (Jeff 02:00) | **Post-chorus** $0 coach in parity eval | MiniMax music API (410) | Not entitled |
| Self-improve (R13 weakest **9.96**) | Round logged in handback + RESULT; focus row from `scores_weakest` | Grok autopilot | Jeff 00:42 |

## R16 build focus (lowest R13 scores first)

1. **Enhancement 3 / dashboard (9.99 → prove tap-through):** `dashboard_plain[].action` → Jobs cards scroll + highlight (Top, Also running, More live jobs).
2. **Self-improve loop (9.96):** Document R16 in handback + RESULT; verified READY ship gate unchanged.
3. **Music (9.99):** **Post-chorus** coach parity case ($0).
4. **Failover (TOP):** `WEBCHAT_HANDBACK_TAG=r16` isolated drill ×2; `prod_unchanged: true`; ts.net ready drill.
5. **Web Bob vs Bob:** 48-task eval must **beat** Bob.

## Council

Gemini + MiniMax + Claude via `council.py`; synthesizer vote; no Grok.

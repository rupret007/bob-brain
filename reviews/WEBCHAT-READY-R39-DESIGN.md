# Web Bob Round 39 — design note (research-first, on R37/R38 baseline)

**Date:** 2026-09-27 CT · **Branch:** `draft/webchat-failover-20260927` · **Baseline:** R37 RESULT + R38 design (unshipped) · **No Grok.**

## Research pass

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| R36/R37 remaining risk | Handback drill **prod_race_retries** when autopilot touches STATE/CATCHUP | Ignoring fingerprint drift | Fail-closed `prod_unchanged` still required on success |
| ADDED 02:03 dashboard | Full pipeline table in RESULT + `e2e_live.py --isolated` | Skip E2E again | R36 deferred costly loop; R39 runs isolated proof |
| R37 lowest rows | Enhancement 2 **9.98**, Conductor **9.98** | New music API | Jeff 02:00 — 410 not entitled |
| web.dev contrast | Stronger `.call-you` accent (Jeff) vs muted Bob lines | Same weight for both speakers | Voice tied lowest with enhancement 2 |
| Apple HIG | 44pt mic/call unchanged | Re-open tab layout | R36 iPhone tab bar stable |

## R39 build focus (lowest R37 scores first)

1. **Failover (TOP):** handback drill ×2 (`r39-1`, `r39-2`), `prod_unchanged: true`, reverse + `events_ok`; retry on autopilot race.
2. **Enhancement 2 (9.98):** inherited `parse_do_more` + queue cards; document proof in RESULT.
3. **Conductor parity (9.98):** council + drills env on `start.sh`; no read-only regression.
4. **Voice (9.99):** live call transcript Jeff vs Bob line contrast (CSS).
5. **Dashboard (02:03):** detailed live dashboard section + isolated E2E provider loop.

## Council

Gemini + MiniMax + Claude via `council.py`; vote on disagreements; no Grok.

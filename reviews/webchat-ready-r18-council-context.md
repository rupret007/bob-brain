# Round 18 council context (Web Bob on R27)

**Branch:** `draft/webchat-failover-20260927` · **Design:** `WEBCHAT-READY-R18-DESIGN.md` · **Baseline:** R27 `4b6fb34` · **No Grok.**

## Ship gates (hold until RESULT + artifacts)

1. **109** webchat + **23** failover + **53** services tests PASS
2. Bob parity **36/36** (`bob_parity_eval.py`)
3. `WEBCHAT_HANDBACK_TAG=r18` handback drill **×2** (`prod_unchanged: true`)
4. Live ts.net ready drill + merge refusal
5. `iphone-r18` layout metrics ≥0.75 (390×844, 430×932)
6. `node conductor/webchat/test_quiet_hours_js.mjs`
7. Council via `conductor/services/council.py` (Gemini, MiniMax, Claude)

## R18 delta (lowest R27 scores + iPhone-first)

- **iPhone:** Settings tab label; collapsible quick chips; modal backdrop; assistant contrast; hide header Jobs on phone; larger lyrics editor
- **Speed:** panel snapshot cache 1.5s; live_ops sync throttle 2.5s; poll 1s
- **Self-improve:** install nudge in Setup status line
- **Music:** plagal cadence (IV→I) on $0 scan
- **Dashboard:** MiniMax % used + headroom rows on Jobs/Models ops detail

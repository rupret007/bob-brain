# Council context — Web Bob Round 19 (on R32 baseline)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R32 `e7d9f44` · **No Grok.**

## Ship criteria

1. **iPhone-first:** collapsed quick chips default on ≤430px; Prefs tab label + Settings aria; view-enter animation; assistant bubble contrast; `iphone-r19` screenshots ≥0.75 message ratio.
2. **Voice:** live call TTS uses `speakRateValue()` (same as auto read-aloud).
3. **Dashboard:** `Also running` plain row when two live screen jobs.
4. **Music:** pre-chorus coach eval case ($0).
5. **Failover:** `WEBCHAT_HANDBACK_TAG=r19` handback ×2 `prod_unchanged: true`; ts.net ready drill.
6. **Tests:** webchat + failover + services + bob parity + quiet hours JS.

## Questions for council

- Is **Prefs** vs **Settings** label acceptable with aria-label?
- Does second-job row belong in plain grid or only Jobs cards?

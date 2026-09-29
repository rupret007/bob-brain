# Round 20 council context (on R35 baseline)

**Candidate changes (iPhone-first):**
- Tab label **Settings** (was Prefs); assistant bubble contrast; modal dim 0.58→0.78; live-call transcript readability.
- Handback drill prod fingerprint **6×2s** retry (`prod_quiet_attempts`).
- Music: ABABCB song-form coach + parity **54/54**.
- iPhone evidence: `iphone-r20` + modal screenshots at 390×844 and 430×932.

**Gates:** 116 + 23 + 64 tests; `WEBCHAT_HANDBACK_TAG=r20` ×2; `live_ready_drill.py` ts.net; parity 54/54.

**Priority if scope slips:** failover → iPhone contrast/modal → handback retry → song-form coach.

**Vote:** ship draft after gates or hold?

# Round 14 council context (refresh on R20 baseline)

**Branch:** `draft/webchat-failover-20260927` · **Baseline:** R20 final `c84662a` · **No Grok.**

## Changes (R14 on R20)

1. **`job_queue.py`:** `Ask the council to …` natural parse alongside `run council on:`.
2. **`live_dashboard.py`:** Weakest score row appends `· {headroom_to_10} to 10` when focus present.
3. **`app.py`:** Panel enrich passes `scores_weakest_focus` into live ops bundle.
4. **`static/style.css`:** Mic + call-in-pill contrast (voice 9.97 target).
5. **`static/app.js`:** Council quick-action + conductor prompts plain English.
6. **`safe_restart.sh` / `deploy_restart.py`:** Authenticated panel verdict + single-PID SIGTERM drain (gentle deploy).
7. **`bob_parity_eval.py`:** +dispatch/worker allowlist + natural council case (**57** tasks).

## Gates

- `python3 conductor/webchat/test_webchat.py`
- `python3 conductor/webchat/test_failover.py`
- `python3 conductor/services/test_services.py`
- `bob_parity_eval.py` **57/57**
- `WEBCHAT_HANDBACK_TAG=r14` handback ×2
- `live_ready_drill.py` ts.net
- Restart `127.0.0.1:8787` after deploy

Question: Ship draft round 14 after gates? Blockers?

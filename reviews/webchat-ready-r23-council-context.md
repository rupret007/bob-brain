# R23 council context (Round 23 on R17)

**Branch:** `draft/webchat-failover-20260927`  
**Baseline:** R17 `5e8fa8b` · **Pre-R23 HEAD:** `02787e9`

## Changelog (phone-visible)

- **iPhone-first:** Queued scheduler jobs show as dashed **Jobs** cards (`Next up` / `#N in queue`); per-message Copy hidden on ≤430px (long-press menu kept); subtle message bubble depth.
- **Live dashboard:** Jobs/Models ops detail uses **`scores_measured_at`** (latest RESULT mtime), not ops snapshot `generated_at`.
- **Failover:** handback `r23-1` / `r23-2` ×2, `prod_unchanged: true`.
- **Tests:** 98 + 24 + 66 OK; Bob parity **58/58**; ready drill p50 **1.182s** ts.net; `e2e_live --isolated` PASS.

## Diff touch list

- `conductor/webchat/static/app.js` — `buildQueuedJobCard`, `formatScoresMeasured`, `renderLiveJobs(..., queued_jobs)`
- `conductor/webchat/static/style.css` — `.queued-job`, mobile hide `.msg-copy`, bubble shadows
- `conductor/webchat/test_webchat.py` — static regression for queue + measured-at
- `conductor/reviews/WEBCHAT-READY-R23-DESIGN.md`

## Question

Round 23 Web Bob: iPhone Jobs queue cards, scores measured-at honesty, failover r23×2. Ship draft RESULT after gates? No Grok.

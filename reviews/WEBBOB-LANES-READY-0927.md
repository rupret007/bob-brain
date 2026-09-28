# Web Bob lane visibility (0927)

## Summary

Web Bob now reads Bob the Bot’s detached `lane-*` `screen` sessions the same way the mini does: `screen -ls` plus `ps` for the worker command, mapped to `logs/*-prompt.txt`, lane logs, and `reviews/*.md` result files.

## What shipped

- **`webchat/lane_collector.py`** — read-only collector: live `lane-*` rows (LLM/model, project, task from prompt, elapsed time, result path) and **finished lanes within 12 hours** with their report file.
- **`live_status_snapshot`** — embeds `bob_lanes` in every provider context block.
- **`reply_authority`** — status replies are answer-first, **one line per lane**, plus non-lane “Other sessions” and idle/cooldown providers.
- **`jobs_view`** — Jobs tab cards use lane collector metadata; recently finished merges queue jobs with lane reports (up to 5).
- **`webchat/test_lane_collector.py`** — fixture `screen`/`ps` regressions.

## Verification

```bash
bash reviews/run-webbob-tests.sh
python3 webchat/bob_parity_eval.py
```

- **webchat + services tests:** 277 passed  
- **services pytest:** 121 passed  
- **quiet_hours_js:** OK  
- **bob_parity_eval:** 30/31 (9.68)

## Deploy

**Not deployed** (per request). Merge via draft PR only after review.

## Risks

- Review file matching is token-heuristic when the prompt omits an explicit `reviews/…` path.
- Finished-lane window is 12h from prompt/log/review mtimes; a lane with no prompt file on disk will not appear in history.

# Round 25 Web Bob diff context
**Focus:** status cache invalidation on ledger mutate; live ops `queue_next_preview` + `tracked_job_count`; dominant (V) chord hint; `start a job for me` do-more path.
**Baseline:** R24 final `0ca013d`. Handback `r25×2` + ts.net drill required.

## Key files
- `conductor/state/ledger.py` — `invalidate_status_snapshot()` on `_mutate`
- `conductor/services/live_dashboard.py` — queue preview + tracked count in `public_live_ops`
- `conductor/webchat/static/app.js` — ops detail rows Next queued / Tracked jobs
- `conductor/webchat/job_queue.py` — DO_MORE before parse_start; new phrase
- `conductor/webchat/music_notebook.py` — Dominant (V) line on progression scan
- Tests: `test_status_snapshot_invalidates_after_open_ask`, `test_public_live_ops_carries_queue_next_preview`, parity 30/30

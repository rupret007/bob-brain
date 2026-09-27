# Web Bob live context — RESULT (2026-09-27)

**Branch:** `draft/webbob-live-context-0927`  
**Scope:** Snapshot + prompt building only (no job-runner, queue claim, or service restarts).

## Problem

MiniMax told Jeff it did not know what workers were doing. Fast-path and full prompts included handoff files and `compact_digest`, but not a single authoritative live view of screen sessions, job journal state, lane logs, service health, and disk—so API providers could honestly (but wrongly) disclaim worker visibility.

## Fix

1. **`webchat/live_status_snapshot.py`** — `build_live_status_snapshot(root)` (read-only):
   - **Screen lanes:** every `screen -ls` session with role (service / job / other) and a `doing` line (from `load_live_ops` when present, else journal/screen heuristics).
   - **Queue jobs:** latest rows from `conductor/jobs.jsonl` and `conductor/queue.jsonl` (if present), bucketed as `queued`, `claimed`, `done`, `failed`, with **worker** (`engine` / `lane` / `screen:<job_id>`).
   - **Lane log tails:** `conductor/status/notes-<lane>.md`, `logs/<lane>.log`, and service `logs/*.log` tails for busy or active lanes.
   - **Service health:** heartbeat age + `svc-*` screen presence (same four services as runtime).
   - **Disk:** `df` summary for the repo root.
   - **Instruction** string telling models to cite this block and not claim blindness when data is present.

2. **`webchat/providers.py`** — Every turn (lite and full) appends a Reference snapshot part:
   - `live_status_snapshot (every turn; cite for worker/status questions)`
   - RULES updated: status/worker answers must quote fields from that snapshot.

All providers share the same `Providers.prompt()` → **gemini, minimax, codex, cursor, and claude** receive identical live context on each chat turn.

## Tests

| Test | File | Status |
|------|------|--------|
| `test_live_status_snapshot_builder_reads_jobs_and_lanes` | `webchat/test_webchat.py` | Added |
| `test_gemini_prompt_includes_live_status_snapshot` | `webchat/test_webchat.py` | Added |
| `test_minimax_call_receives_live_status_snapshot_prompt` | `webchat/test_webchat.py` | Added |

**Commands run**

```bash
python3 -m py_compile webchat/live_status_snapshot.py webchat/providers.py
# Standalone prompt tests (Providers + snapshot, no app import):
cd webchat && python3 -c '…'  # gemini prompt + minimax call — PASS
```

**Note:** `python3 webchat/test_webchat.py` currently fails at import in this worktree (`parse_do_more` missing from `job_queue.py`, unrelated to this change). New tests are in that suite for when the import chain is fixed.

## Changed files

- `webchat/live_status_snapshot.py` (new)
- `webchat/providers.py`
- `webchat/test_webchat.py`
- `reviews/WEBBOB-CONTEXT-0927.md`

## Remaining risks

- Live ops enrichment depends on `load_live_ops` / `dashboard.json`; when stale, screen list and `jobs.jsonl` still populate the snapshot, but `doing` lines may be thinner until dashboard refresh.
- `screen -ls` and `df` are best-effort in sandboxes without those binaries.
- Models can still ignore instructions; hollow-progress guard in `reply_guard.py` is unchanged.

## Verification status

| Check | Result |
|-------|--------|
| `py_compile` on changed modules | **PASS** |
| Standalone gemini/minimax prompt tests | **PASS** |
| Full `test_webchat.py` | **BLOCKED** (pre-existing `parse_do_more` import) |
| Service restart | **Not performed** (per request) |

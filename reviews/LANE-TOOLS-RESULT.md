# Web Bob tool layer — lane-tools result

**Branch:** `draft/lane-tools-0927` · **Final SHA:** `d3f4bc775133ae75aa46cc1c24ce6515fa668482`
**Source:** `conductor/WEBCHAT-READY.md` §`04:18` — *"P0 TOP-1: Web Bob must stop being read-only (Jeff: "I need you to do more"; dislikes the limits)"*
**Scope given:** build ONLY the allowlisted tool layer (webchat/ tools module + system prompt) with the hard blocks from that section; do not touch `services/job-runner`; commit + push to this draft branch; never merge.

## What shipped

- **`webchat/tools.py`** (new) — the allowlisted tool layer. Every call goes through `dispatch(name, args, root=...)`:
  1. `name` must be in `_HANDLERS` — nothing else is reachable, including anything an LLM might invent.
  2. name+args are scanned against 7 hard-block patterns (below) *before* the handler runs.
  3. the handler executes and returns `{ok, summary, data?, undo?}`.
  4. the call is appended to `conductor/state/events.jsonl` via `alignment_events.append_event` (actor, tool, args, ok, undo, undo_expires_at) — this is the "shows as a card with 30s undo" requirement from the spec.
- **19 tools**: `read_file`, `queue_add`, `queue_split`, `queue_prioritize`, `queue_set_status`, `queue_cancel`, `queue_cancel_many`, `request_lane_start`, `request_lane_stop`, `run_council`, `run_tests`, `run_drill`, `git_status`, `git_diff`, `git_branch`, `git_commit`, `git_push`, `open_draft_pr`, `read_ci`. `list_tools()` exposes them with JSON-schema-style `input_schema` for future function-calling wiring.
- **`tools.undo(event_seq, root=...)`** — generic 30s-window undo: replays the inverse action recorded on the original event (e.g. `queue_prioritize` restores the old priority; `queue_add`/`run_council` cancel the row they created; `request_lane_start` undoes to `request_lane_stop`). Expired or absent undo payloads raise a typed `ToolError`.
- **System prompt (`webchat/providers.py: RULES`)** — removed the "This is a read-only chat" framing and the "cannot spawn tools mid-reply" dead-end. Web Bob is now told it **is the conductor when Bob is away**, has the real tool layer above, and must tell Jeff the exact command instead of deferring to Bob/Jeff — while still never claiming it executed something mid-reply that didn't happen (the LLM itself still can't call `tools.py` directly; see Architecture note).
- **One additive wire-in (`webchat/app.py`)** — `tools.try_capability_reply(text)`, checked right after the existing `sync_from_live_ops` block and before `music_tip`, following the exact pattern already used for `try_music_coach_reply` / `try_bob_state_running_line` / `try_status_reply`. It pattern-matches Jeff's actual complaint ("I need you to do more", "stop being read-only", "you're too limited", "just do it", etc.) and answers with the real tool names and how to invoke them — resolved entirely in Python, before any LLM call.

## Hard blocks (from §04:18, enforced in `_scan_hard_blocks`)

| Block | How |
|---|---|
| Merge | regex on name+args; also: no tool named `merge*` exists |
| Undraft | regex (`undraft`, `gh pr ready`, `--ready`); `open_draft_pr` hardcodes `--draft`, never a parameter |
| Force-push | regex (`--force`, `force-push`, `+refs/`); `git_push` takes no flags — argv is fixed `git push -u origin <branch>` |
| Send texts/emails/DMs/posts | regex; also: no such tool exists at all |
| Spend past cap | `run_council` reads `conductor/ledger/minimax.jsonl` and refuses once committed spend ≥ `billing.MINIMAX_CAP_USD`; regex also blocks `buy`/`purchase`/`subscribe`/`upgrade plan`/`change login` |
| Delete outside a worktree | no delete tool exists; `_safe_repo_path` rejects `..`, absolute paths, and anything outside `root` for `read_file`/`git_diff`/`git_commit` paths; regex also blocks `rm -rf`/`git clean -f`/`reset --hard` |
| Grok as a worker | regex on every tool call, including lane names and council questions |

Mutating git/PR actions (`git_commit`, `git_push`, `open_draft_pr`) additionally require the current branch to start with `draft/` (`_require_draft_branch`), checked via `git symbolic-ref` — not trusted from caller input.

## Lane control ≠ job-runner

`request_lane_start`/`request_lane_stop` **only append an event** (`lane_start_request` / `lane_stop_request`) to `conductor/state/events.jsonl`. They never call `run()`, never touch `screen`, and never import anything under `services/`. `test_lane_request_never_spawns_a_process` asserts `tools.run` is not called for these two tools. The scheduler (a separate lane, `draft/lane-scheduler-0927`) decides whether to act on the request — this stays entirely on the data side of that boundary.

## Architecture note (why the LLM still can't call these directly)

Today, Web Bob's only *deterministic* action layer is the pre-LLM regex parser in `app.py:Chat.submit()` (`parse_start`, `parse_council`, and now `try_capability_reply`) — these intercept Jeff's literal text and act **before** any model is invoked; the model never sees those messages. Wiring real function-calling into four different CLI backends (Gemini/Claude/Codex/MiniMax) so the *model itself* can call `tools.dispatch()` mid-reply is a materially larger change than "build the tool layer + system prompt," so it's out of scope here by design. This round makes the capability real and testable (`tools.py` + one additive `app.py` branch) and makes the prompt honest about it; wiring the model itself into `dispatch()` is a natural follow-up round once this lane and `lane-scheduler` both land.

## Tests

| Suite | Result |
|---|---|
| `python3 conductor/webchat/test_tools.py` (new, 48 tests) | **PASS** — hard blocks (7), queue tools + undo, lane requests (incl. "never spawns a process"), council + cap refusal, tests/drills sandboxing, git status/diff/branch/commit/push (real temp repo + local bare remote), `open_draft_pr`/`read_ci` (mocked `gh`, asserts `--draft` always present / `--force` never present), capability-reply detection, and the **replay test** below |
| `python3 conductor/webchat/test_webchat.py` (existing, 69 tests) | 68 pass; 1 pre-existing, unrelated failure — `test_job_card_view_from_events` (`ModuleNotFoundError: job_card_view`), confirmed present on baseline `cfa72d6` before any of this lane's changes (stashed and re-ran to verify) |
| `python3 conductor/webchat/test_failover.py` (existing, 23 tests) | **PASS**, unaffected |
| `python3 -m py_compile` on all touched/added files | **PASS** |

### Replay test: "I need you to do more"

`ReplayCapabilityChatTests.test_replay_i_need_you_to_do_more` drives the real `Chat.submit()` with a `FakeProviders` whose `reply()` raises if ever called. Submitting `"I need you to do more"`:
- returns status `done` in the same call (no queued/running LLM turn — `self.fake.calls == []`),
- reply text names concrete tools (`queue_add`, `run_council`, `git_status`, `open_draft_pr`),
- does **not** contain the old "This is a read-only chat" phrasing or "Bob or Jeff [must do it]".

## Explicitly not done (scope)

- No changes anywhere under `services/` (confirmed via `git diff --stat`: only `webchat/app.py`, `webchat/providers.py`, plus the two new `webchat/` files).
- No live-wiring of `tools.dispatch()` into the model's own turn (see Architecture note) — `try_capability_reply` is the one deterministic, pre-LLM hook, matching this codebase's existing `try_*_reply` pattern.
- No natural-language command parser for the *new* tools (prioritize/cancel/git/PR/CI/tests/drills) inside `Chat.submit()` — `dispatch()`/`list_tools()` are ready for that wiring, left for a follow-up round to avoid touching the same hot path other lanes are also working in.

## Push

Committed to `draft/lane-tools-0927` (`d3f4bc7`) and pushed. Not merged — draft only, per standing rules.

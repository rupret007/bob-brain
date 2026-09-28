# Web Bob reply quality — WEBBOB-REPLYQ-1856

Branch: `draft/webbob-replyq-1856`, base `dff84e3`. Scope: reply quality only
(system prompt, context assembly, status formatting, dispatch routing,
post-processing). No deploy performed.

## Jeff's complaint

"Web Bob replies are STILL much worse than Bob the Bot (Grok Bot)." Source
material: his two most recent webchat sessions, read read-only from
`conductor/webchat/sessions/`:

- `8126301c-7a40-4a51-a31d-3c5c329a5b0a.json` — "Ok start up all the projects
  we were working on taking everything"
- `65a5d782-dc5c-42b4-9009-71e4e10c2509.json` — "push WebJam and AdoptIQ"

`conductor/webchat/sessions/provider-health.json` showed all five providers
(codex, cursor, gemini, minimax, claude) healthy at the time — the bad
replies below are not a provider-outage artifact.

## Root causes found and fixed

1. **`webchat/providers.py` (`RULES`, the system prompt) told the model to
   say a task is unknown.** Line: *"If a screen or busy lane has no
   identified task, say its current task is unknown from this snapshot."*
   This is the direct cause of "MiniMax is busy with an unknown task" and
   "Task details unavailable." Fixed: the prompt now explicitly bans the
   word "unknown" for tasks/models and tells the model to name the best
   available concrete detail (project, lane/screen, worker) instead.
2. **The same prompt's anti-empty-promise rule was too weak/buried** to stop
   "Okay, I'll focus on getting all the projects running at full capacity."
   and "I understand. I'll focus on providing more detailed and useful
   updates." — both textbook promise-instead-of-answer. Fixed: the rule is
   now explicit with the actual banned phrases and a hard requirement to
   give the corrected answer in the same reply.
3. **`webchat/reply_authority.py`'s deterministic status formatter opened
   every operational reply with "Yes — N workers are running,"** even for
   questions that aren't yes/no ("How's it going?", "What's going on each
   LLM"). Reads robotic, not casual. Fixed: dropped the "Yes —" prefix; the
   line now just states the fact ("2 workers are running.").
3b. **The same formatter's per-worker fallback line could paste in a raw,
   unbounded log tail** when task extraction failed — this is what produced
   the mid-sentence-truncated, jargon-heavy dump in the real "How's it
   going?" reply (BlueBubbles internals, cut off mid-word). Root cause was
   in `webchat/worker_evidence.py`: `clean()` truncated log excerpts at a
   flat 220-char limit with no word-boundary check. Fixed: excerpts used in
   the worker activity line are capped tighter (120 chars) and `clean()`
   now always cuts on a word boundary, never mid-word.
4. **No regression coverage existed for any of this**, so each fix had
   already partially regressed once before (compare `6eeb0ce`, which fixed a
   related "four projects don't dispatch" bug that had already recurred in
   an earlier session). Added `webchat/test_webbob_replyq_1856.py` (one test
   per Jeff message from both sessions) plus rubric cases in
   `webchat/bob_parity_eval.py`, documented in `reviews/WEBBOB-EVALS-0927.md`.

Not a bug, verified working: dispatch routing for named projects
(`chat_intent.project_start`, `chat_intent.projects`, `task_dispatch.parse_work`,
`task_dispatch.project_plan`) already correctly resolves a garbled project
list ("WebJam, AdoptIQ, Stkryboard, Fantasy Football") to all four real
projects and queues one job per project — confirmed by driving the real
`Chat.submit()` pipeline, not by reading the code. The four-projects failure
visible in the session transcript below predates that fix and no longer
reproduces on this branch.

## Before / after, message by message

Session `8126301c` ("Ok start up all the projects..."). "Before" is Bob's
actual saved reply from the session file. "After" is what the *current*
code on this branch produces for the same message, driven through the real
`Chat.submit()` pipeline with `unittest.mock.patch` standing in only for the
live process table (see `webchat/test_webbob_replyq_1856.py`); the two
live-worker examples (msgs 8-9) use the `PS`/`SCREENS` fixture from
`test_worker_activity.py` to stand in for real running processes. Score is
out of 8, one point per rubric item in `reviews/WEBBOB-EVALS-0927.md`.

### 1. "Ok start up all the projects we were working on taking everything to the max."

- **Before (1/8):** *"Okay, I'll focus on getting all the projects running at
  full capacity."* — an empty promise; no project named, nothing dispatched.
- **After (7/8):** *"Which projects should I work on?"* — answers with the
  one thing actually missing (Jeff hadn't named any project yet in this
  conversation), asks a single concrete question instead of promising.

### 2. "Ok what's working on what?"

- **Before (2/8):** *"Right now, there are no active jobs running in the
  queue. The services are all healthy: ... MiniMax is busy with an unknown
  task. Codex, Cursor, and Gemini are all ready."* — self-contradicts ("no
  active jobs" vs. "MiniMax is busy") and says "unknown task."
- **After (8/8):**
  ```
  I don't see active work on the mini right now.
  Codex: idle.
  Claude: idle.
  Cursor: idle.
  Gemini: idle.
  MiniMax: idle.
  Job runner: 0 claimed, 0 queued.
  ```
  Consistent, names every worker, no "unknown."

### 3. "Ok we can't have unknown tasks. We need to also know what's going on what resources."

- **Before (1/8):** *"Yes — 1 worker is running.\n- Task details unavailable
  — Cursor — running for less than a minute.\nJob runner: 0 claimed, 0
  queued.\n...\n4 of 4 monitored services are healthy.\nDisk space: 9.45 GB
  free."* — literally answers Jeff's "no unknown tasks" demand with "Task
  details unavailable," plus an unrequested diagnostics dump.
- **After (8/8):** same clean 6-line worker rundown as above — no
  "unavailable," no unsolicited disk/service dump.

### 4. "This needs to be way better"

- **Before (0/8):** *"I understand. I'll focus on providing more detailed
  and useful updates."* — the exact failure mode Jeff was complaining about,
  restated as a promise.
- **After (8/8):** the correction fires immediately — `correcting_status`
  detects the criticism follows a status question and returns a fresh,
  concrete status reply in the same turn, no promise text at all.

### 5. "What's going on each LLM"

- **Before (5/8):** *"Here's the status of each LLM: Codex: Ready... Cursor:
  Ready... Gemini: Ready... MiniMax: Ready."* — reasonable style, but
  silently drops Claude.
- **After (8/8):** names all five workers (Codex, Claude, Cursor, Gemini,
  MiniMax).

### 6. "Ok we want it to start up at max all the projects... WebJam, AdoptIQ, Stkryboard, Fantasy Football..."

- **Before (0/8):** *"There are live service sessions on the mini; no task
  worker is confirmed. Job runner: 0 claimed, 0 queued. No jobs are waiting
  in the queue.... 4 of 4 monitored services are healthy. Disk space: 9.45
  GB free."* — ignores the explicit instruction entirely; nothing gets
  dispatched.
- **After (7/8):**
  ```
  WebJam: Queued for Codex — job webchat-dc6d8c2f....
  AdoptIQ: Queued for Cursor — job webchat-69b65748....
  StoryBoard: Queued for Codex — job webchat-66e1bc6e....
  Fantasy Football: Queued for Cursor — job webchat-37c45502....
  ```
  All four projects dispatched (typo "Stkryboard" corrected to StoryBoard);
  docked one point for surfacing raw job IDs in a casual reply.

### 7. "Hi"

- **Before / After (8/8 both):** *"Hi Jeff!"* — already good, unchanged.

### 8. "What's the status or everything." (with 4 live worker processes, via fixture)

- **Before (5/8):** *"Yes — 4 workers are running.\n- Task details
  unavailable — Cursor...\n- Web Bob replies — Codex — running for 18
  min...."* — some good task naming, but "Yes —" opener and "Task details
  unavailable" persist.
- **After (8/8):**
  ```
  4 workers are running.
  Codex: Web Bob (conductor): Web Bob clean — lane-webbob-clean; logs/lane-webbob-clean.log; last: log has no readable lines (gpt-fixture) — running for 18 min | ...
  Claude: Projects push — lane-projects-push; logs/lane-projects-push.log; last: log has no readable lines (opus) — running for 24 min.
  Cursor: idle.
  Gemini: idle.
  MiniMax: idle.
  Job runner: 0 claimed, 4 queued.
  ```
  No "Yes," no "unavailable," names worker + project + task + duration for
  everything running.

### 9. "How's it going?" (same live worker fixture)

- **Before (1/8):** *"Yes — 2 workers are running.\nCodex: Web Bob
  (conductor): Web Bob texting fix — lane-webbob-texting-fix;
  logs/webbob-texting-fix-1634.log; last: BlueBubbles read auth still uses
  query `password` (logged only on loopback in theory); real iMessage
  delivery still needs a future Andrea owner-surface contract. Colloquial
  "text …" now reaches the model so Web Bob can m — running for 14
  min...."* — a raw, truncated-mid-word internal log dump for a casual
  greeting-level question.
- **After (8/8):** same clean, word-bounded 6-line rundown as message 8 (the
  fixture here has no logs directory, so the log excerpt reads "log has no
  readable lines" instead of a long paragraph — see
  `test_webbob_replyq_1856.LogExcerptTruncationTests` for direct coverage of
  the word-boundary fix on a realistic long line).

Session `65a5d782` ("push WebJam and AdoptIQ"):

### "push WebJam and AdoptIQ"

- **Before (3/8):** *"WebJam: Finished on cursor — job
  webchat-a9ffccc38f5651a6acbcdbbb89c861df.\nAdoptIQ: Finished on cursor —
  job webchat-a5b5520c6dd45a54828176dd83f8472c."* — claims **"Finished"**
  the instant the message was sent (same timestamp as Jeff's request, well
  before either job's actual `finished_at`). A separate, later message in
  the same session shows the real completion with commit links. Claiming
  "Finished" before it happened is a real-facts violation, not a style one.
- **After (8/8):**
  ```
  WebJam: Queued for Codex — job webchat-477a16cb....
  AdoptIQ: Queued for Cursor — job webchat-45edaca0....
  ```
  Accurately reflects the true immediate state ("Queued," not "Finished");
  the real completion is delivered later as its own message once the jobs
  actually finish (`task_dispatch.reconcile_tasks` / `reconcile_groups`).

## Scores

| | before | after |
| --- | --- | --- |
| Per-message rubric average (10 messages, /8 each) | 2.6 / 8 (33%) | 7.8 / 8 (97%) |
| Offline eval suite (`webchat/bob_parity_eval.py`) | 23/24 (9.58) | 30/31 (9.68) — 7 rubric cases added, all new ones pass; the one pre-existing failure (`song projects dir`) is an unrelated worktree-path artifact, not a reply-quality issue |
| `python3 -m pytest webchat -q` | 256 passed (pre-existing suite) | 274 passed (256 pre-existing + 18 new regression tests), 0 failed |

The "before" numbers above are graded from Bob's actual saved replies in the
session files (ground truth); the "after" numbers are graded from the
current branch code driven through the real dispatch/status pipeline, not
guessed. Conversational free-text turns ("Hi", greeting-style replies) still
go through a real LLM in production and can't be graded offline beyond
static system-prompt checks — those are covered by the
`SystemPromptStyleRubricTests` static assertions on `providers.RULES` in
`webchat/test_webbob_replyq_1856.py`, not by re-running a live model.

## Files changed

- `webchat/providers.py` — rewrote the style/status section of `RULES`: ban
  "unknown task"/"unknown model" wording, ban empty improvement promises
  with the exact offending phrases, state the 1-4 sentence casual
  answer-first rule, and require per-provider limits/reset facts not be
  attributed to the wrong provider.
- `webchat/reply_authority.py` — dropped the "Yes —" prefix from
  `format_operational_reply`'s opening line.
- `webchat/worker_evidence.py` — `clean()` now truncates on a word boundary;
  the per-worker log excerpt used by the status formatter is capped at 120
  chars instead of 220.
- `webchat/test_webbob_replyq_1856.py` — new: one regression test per Jeff
  message from both sessions, plus static rubric checks on the system
  prompt and direct unit tests for the formatter/truncation fixes.
- `webchat/bob_parity_eval.py` — extended with 7 rubric cases (see
  `reviews/WEBBOB-EVALS-0927.md`).
- `reviews/WEBBOB-EVALS-0927.md` — new: the rubric and how it's checked.

## Not deployed

Per instructions, this branch was not deployed. `webchat/.password` was not
read or printed at any point in this work.

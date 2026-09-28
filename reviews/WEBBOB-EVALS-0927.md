# Web Bob reply-quality eval suite (WEBBOB-EVALS-0927)

Created as part of WEBBOB-REPLYQ-1856. No prior version of this file existed
in the repo, so this establishes the rubric and wires it into the existing
offline eval harness (`webchat/bob_parity_eval.py`).

## Why

Jeff: "Web Bob replies are STILL much worse than Bob the Bot (Grok Bot)." His
two most recent webchat sessions
(`conductor/webchat/sessions/8126301c-7a40-4a51-a31d-3c5c329a5b0a.json`,
`conductor/webchat/sessions/65a5d782-dc5c-42b4-9009-71e4e10c2509.json`) show
concrete, repeatable failure modes, not vague dissatisfaction. This rubric
turns each one into a checkable property.

## Rubric (per reply)

A reply is scored against seven checks. Each is a hard pass/fail, not a
vibe:

1. **Answer-first** — the first sentence answers the question; no throat-clearing.
2. **Casual, bounded length** — 1-4 plain-spoken sentences for a normal chat
   turn. Multi-worker status rundowns may run one short line per worker, but
   every line is a fact Jeff asked for, not filler.
3. **Real facts only** — nothing stated that the live snapshot / job queue
   does not actually support. No "I'll check" without a result attached.
4. **Names worker + LLM + task** — a status answer says *which* worker
   (Codex/Claude/Cursor/Gemini/MiniMax) is doing *what* (project or task
   label), never a bare "something is running."
5. **Never "unknown task"** — if the snapshot has no one-line task summary,
   name the lane/project/screen instead of the word "unknown."
6. **No dumps** — no raw job IDs, PIDs, or full log tails unless Jeff asked
   for diagnostics; a short, word-bounded log excerpt is fine, a run-on
   paragraph mid-word cut off is not.
7. **No empty promises** — "I'll focus on...", "I understand, I'll...", "I'll
   do better" are always a fail. When Jeff says an answer needs to be
   better, the very next reply must *be* better, not promise to be.
8. **Actually starts jobs when asked** — a request naming real projects to
   push/develop dispatches a job per project; it does not degrade into a
   status report or a vague acknowledgement.

## Automated checks (`webchat/bob_parity_eval.py`)

Five rubric checks were added to the existing 24-case offline eval (now 31
cases, run via `python3 webchat/bob_parity_eval.py`):

| case | what it guards |
| --- | --- |
| `prompt bans 'unknown task' wording` | `providers.RULES` no longer instructs the model to call a task "unknown"; it explicitly bans saying so |
| `prompt bans empty improvement promises` | `providers.RULES` explicitly forbids "I'll focus on...", and requires the corrected answer immediately |
| `prompt requires casual answer-first style` | `providers.RULES` states the 1-4 sentence, answer-first rule in plain language |
| `prompt keeps per-provider limits from crossing over` | `providers.RULES` tells the model never to attribute one provider's cap/reset time to another |
| `status reply skips robotic 'Yes —' prefix` | `reply_authority.format_operational_reply` no longer opens every status reply with "Yes —" regardless of whether the question was yes/no |
| `log excerpts truncate on a word boundary` | `worker_evidence.clean` never hands back a word chopped in half |
| `garbled project list still resolves all four names` | typo-tolerant project-name matching (`Stkryboard` → StoryBoard) still works for `chat_intent.projects` |

These are deterministic (no live LLM calls), so they run in CI. Rubric items
1-3 and 7 (tone/promise-avoidance in genuinely free-text LLM replies) cannot
be fully verified offline — the system prompt is the lever available without
a live model call; regression coverage for the deterministic paths (status
formatting, dispatch routing) lives in `webchat/test_webbob_replyq_1856.py`.

## Regression tests (`webchat/test_webbob_replyq_1856.py`)

One test per Jeff message from both sessions above, replaying it through the
real `Chat.submit()` pipeline (not a mock of the decision logic) and
asserting the specific failure mode from the transcript is gone. See
`reviews/WEBBOB-REPLYQ-0927.md` for the before/after transcripts these tests
pin down.

## Running

```
python3 webchat/bob_parity_eval.py            # scored eval, JSON to stdout + webchat/evidence/
python3 -m pytest webchat/test_webbob_replyq_1856.py -q   # regression tests
python3 -m pytest webchat -q                  # full suite
```

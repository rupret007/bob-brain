# Web Bob reply-quality and texting eval notes (WEBBOB-EVALS-0927)

This file preserves the integrate notes from `a777736` and the historical
texting evidence carried by `9751346`. The earlier 24-, 31-, and 33-case
counts describe earlier stages of the harness, not a score for this combined
tip. Integrate's current regression test expects 96 offline cases. Fresh
combined-tip validation is recorded separately in `TEXTING-FIXED-0420.md`
and `TEXTING-READY-0420.md` (or `TEXTING-STILL-FAIL-0420.md`) in the conductor
review directory. Prior LIVE approvals do not approve this combined SHA;
fresh LIVE Gemini and MiniMax reviews are required before any deployment.

## Integrate reply-quality rubric and gate history

Originally created as part of WEBBOB-REPLYQ-1856, this rubric was wired into
the existing offline eval harness (`webchat/bob_parity_eval.py`).

## Why

Jeff: "Web Bob replies are STILL much worse than Bob the Bot (Grok Bot)." His
two most recent webchat sessions
(`conductor/webchat/sessions/8126301c-7a40-4a51-a31d-3c5c329a5b0a.json`,
`conductor/webchat/sessions/65a5d782-dc5c-42b4-9009-71e4e10c2509.json`) show
concrete, repeatable failure modes, not vague dissatisfaction. This rubric
turns each one into a checkable property.

## Rubric (per reply)

A reply is scored against eight checks. Each is a hard pass/fail, not a
vibe:

1. **Answer-first** — the first sentence answers the question; no throat-clearing.
2. **Casual, bounded length** — 1-4 plain-spoken, complete sentences for normal chat
   and multi-worker status. Only requested diagnostics expand the output.
3. **Real facts only** — nothing stated that the live snapshot / job queue
   does not actually support. No "I'll check" without a result attached.
4. **Names worker + LLM + task** — a status answer says *which* worker
   (Codex/Claude/Cursor/Gemini/MiniMax) is doing *what* (project or task
   label), never a bare "something is running."
5. **Never "unknown task"** — if the snapshot has no one-line task summary,
   name the lane/project/screen instead of the word "unknown."
6. **No dumps** — no raw job IDs, PIDs, or full log tails unless Jeff asked
   for diagnostics; casual replies use readable task labels and observed model metadata.
   Raw logs belong only in requested diagnostics.
7. **No empty promises** — "I'll focus on...", "I understand, I'll...", "I'll
   do better" are always a fail. When Jeff says an answer needs to be
   better, the very next reply must *be* better, not promise to be.
8. **Actually starts jobs when asked** — a request naming real projects to
   push/develop dispatches a job per project; it does not degrade into a
   status report or a vague acknowledgement.

## Automated checks (`webchat/bob_parity_eval.py`)

Seven rubric checks were added to the existing 24-case offline eval (31
cases at that stage, run via `python3 webchat/bob_parity_eval.py`):

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

## Cross-vendor gate corrections

At this gate the suite grew to 33 cases, required 33/33, and initialized isolated
data in any worktree. Three always-true assertions were repaired; the directory check
was replaced with a real song save/reload. New cases cover complete, bounded
status sentences and ID-free task/worker receipts. A green offline score is
not a claim that Web Bob beat another model. See `WEBBOB-REPLYQ-GATE-0927.md`
and the actual live gate evidence for the final deployment decision.

## Historical offline Web Bob eval evidence — 1841 texting gate

The recorded result at the isolated texting gate was **24/24 existing offline
checks passed**, plus **3/3 stricter status checks**. This is not a run or score
for the combined tip. Raw cases, run time and source hashes are preserved in
[WEBBOB-EVALS-0927.json](WEBBOB-EVALS-0927.json).

This ran `webchat/bob_parity_eval.py::run_eval` in a fresh synthetic data root
inside this worktree. It did not call live services, live models or messaging.
It covers work routing, worker allowlisting, job/council parsing, handback state,
status and music hooks. It does not replace same-tip LIVE cross-vendor reviews or
prove production message delivery, voice, media, or full live parity.

The status fixture explicitly writes `Synthetic texting validation job` and a
synthetic `deadbeef` SHA using `state_ledger.write_now`. An initial run against an
empty root returned 23/24 because status correctly has no answer without evidence;
the runner expects populated state. The seeded run is recorded here. No runtime
code or expected eval result was changed to obtain the passing count.

Three eval rows in that version used permissive `or True` checks. The additional
checks required the actual replies to “what’s running?”, “quick status”, and
“anything I need to do?” to contain the seeded job text. Integrate subsequently
repaired these assertions as described above. The runner’s generated score and
`web_bob_vs_bob` label in the JSON are not a live comparison verdict.

Historical reproduction command for the isolated texting tree (`9751346`):
the 24-case assertion below does not apply to the combined integrate harness.

```sh
python3 - <<'PYCODE'
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'webchat'))
from bob_parity_eval import run_eval, state_ledger
with tempfile.TemporaryDirectory(prefix='.texting-proof-eval-', dir='reviews') as tmp:
    root = Path(tmp)
    (root / 'conductor/webchat').mkdir(parents=True)
    (root / 'conductor/state').mkdir(parents=True)
    assert state_ledger.try_status_reply(root, 'status') is None
    state_ledger.write_now(root, 'Synthetic texting validation job', sha='deadbeef')
    result = run_eval(root)
    assert result['passed'] == result['total'] == 24
    for prompt in ("what's running?", 'quick status', 'anything I need to do?'):
        assert 'Synthetic texting validation job' in (state_ledger.try_status_reply(root, prompt) or '')
    print('24/24 offline checks and 3/3 strict status checks passed')
PYCODE
```

The conductor must assess this limited offline evidence against its deployment
eval requirement; no unrun LIVE eval is claimed.

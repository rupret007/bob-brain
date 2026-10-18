# Web Bob redeploy fix — 2026-09-27

The 15:22 deployment log records three failed live checks: `going`, `claude161`,
and `push2`. All received HTTP 401 rather than an application response. `go`
was incorrectly marked true despite both hold/go requests also returning 401;
absence of a hold phrase in an HTTP error does not prove a released hold.

The initial worktree command failed because `draft/webbob-minimax-0927` was
already checked out. The deployment continued from dirty `conductor` at
`6e3216d`, so its green tests did not establish that the intended candidate was
deployed. Two attempts to invoke `e2e_live.py` also omitted required `--output`.
The log cannot establish whether the live application satisfied any check.

This branch starts at clean tip `7ab7f1311f70262932a9e8dcc7f78c096e996567`,
which already contains MiniMax implementation `f2af459` and acceptance proof
`855be8b5c9056e4f8d356b958cf6f136504d1ddb`. It retains the clean Jobs UI, live
process/screen observations, durable plain-language dispatch and saved holds.

Rehearsal found two additional exact-phrase gaps: `is it going now?` was not
recognized as server status, and `push WebJam and AdoptIQ` needed extra wording
such as “to the max.” The fix recognizes the progress question and explicit
project lists. A named project push releases only those projects' holds.

`webchat/live_redeploy_check.py` logs in through `/login`, keeps its cookie in
memory, obtains CSRF from `/api/session`, and requires successful HTTP replies.
It checks the exact four prompts against saved conversation state, the real
queue journal, `/api/jobs`, and read-only screen/process observations. Detailed
status must include every stable screen, including service screens. Replayed
requests must not duplicate jobs. Hold/go must persist both transitions and
answer a subsequent hold question without reviving the cleared hold. Every
exception fails its named check; authentication failure fails all four.

Validation: 241 chat tests, 111 service tests, JavaScript quiet-hours test,
bootstrap syntax, JavaScript syntax, and diff whitespace checks passed. All four
checks passed against an isolated authenticated listener with real private queue
writes and model generation forbidden. The existing Jobs browser proof passed
at 320/390/430/900 px in light/dark modes, including unavailable sources and
actual read-only host observations. No live services were changed by rehearsal.

Live invocation (creates three real draft-only jobs):

```sh
python3 webchat/live_redeploy_check.py --root /path/to/bob-overnight-inject \
  --output /path/to/live-evidence.json
```

Add `--isolated` to rehearse with temporary state. Credentials are read directly
from the data root and never printed or placed in command arguments. Deployment
must pin both services to a clean, detached checkout, create a fresh rollback
point first, and restore that point on any failed live check. Only webchat and
job-runner are restarted. Final live evidence is recorded in the data root's
`conductor/reviews` and its success or failure handoff file.

# Offline Web Bob eval evidence — 1841 texting gate

Actual result: **24/24 existing offline checks passed**, plus **3/3 stricter status
checks**. Raw cases, run time and source hashes are in
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

Three existing eval rows use permissive `or True` checks. The additional checks
require the actual replies to “what’s running?”, “quick status”, and “anything I
need to do?” to contain the seeded job text. The runner’s generated score and
`web_bob_vs_bob` label in the JSON are not a live comparison verdict.

Reproduce from the worktree root:

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

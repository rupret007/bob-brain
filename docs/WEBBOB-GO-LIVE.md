# Staged Web Bob go-live package

Prepared only. No activation has been executed. Jeff's explicit go-live OK is
required after every other gate passes. The candidate stays a draft and this
driver never merges it. No script creates reviews, scores, approvals or sends.

The predecessor commit resolves in this repo to
`cf83a9a80e0426d6998a0bf7b3a0574e52ac8e1a`. This is a source pin, not a fresh
observation of Mini :8787. Before approval, verify the live authenticated local
and public build, both code pins, reminder-state compatibility and the saved
predecessor receipt on Mini. If live has moved, stop and review a new package;
do not replace a newer deployment with this predecessor.

From a clean frozen draft checkout, `python3 release/go_live.py plan` prints a
read-only plan with the exact candidate SHA, rollback pin and required approval
text. It reads git identity; it does not contact or change live services.

`release/go_live.py activate` adds the following admission gates to the existing
controller: Jeff's exact candidate/predecessor OK, complete unscoped release
qualification, exact-head Karen PASS, Claude+Codex main >=144 and holdout PASS,
fresh exact-head GitHub Actions success, and authenticated predecessor versions.
Both native runtime jobs, the root unit job and `public-privacy` must succeed
at that exact SHA. Missing, skipped, pending, failed or stale privacy checks
refuse admission even when the runtime suites are green. Historical privacy
findings remain blockers; this package never suppresses or classifies them.
It then calls `solo.deploy` with `feature=improve` and the fixed full predecessor.
Every existing gate remains, including two latest consecutive full check greens,
hash-verified logs, source/self-review, bridge/media/voice/browser checks,
predecessor receipts, checked-tree merge/base rules and service coordination.
The legacy controller expects its existing `draft/webbob-clean-0927` checked-tree
ancestry; this wrapper neither satisfies that condition nor merges a PR. Any
workflow reconciliation requires review and new qualification, never a bypass.

The existing controller snapshots both code pins, preserves state, freezes the
candidate, creates a private recovery journal before activation and checks two
authenticated local/public live rounds. Any post-activation failure, including
health, startup or evidence-publication failure, restores and authenticates the
immediate predecessor before publishing failure. If recovery fails or the
controller is killed, keep its journal and use the frozen controller's:

```bash
python3 release/solo.py recover-pending --root "$HOME/Documents/bob-overnight-inject" --feature improve
```

The release folder also contains its bound `rollback.sh`. Never delete a pending
journal or guess a different source pin to clear recovery. These commands are
for the authorized future operator; none has been run by this driver.

## Gate packet format

Keep packets and actual runner output in a private operator evidence directory,
outside the repository. Do not fabricate a packet when a runner is inaccessible.
The Mini scoring interface still needs inspection and frozen-SHA input binding.
Only normalize its actual recorded output; the format below does not establish
that the supplied pair-only.sh already emits it.

Both JSON packets have `sha` (full candidate SHA), `verdict: "PASS"`,
`unresolved_blockers: []`, and a nonempty `evidence` list. Each evidence entry is
`{"path": "/absolute/path/to/raw-output", "sha256": "64 lowercase hex digits"}`.
Raw output must be a regular file beneath the packet directory; the wrapper
hash-checks it before activation. Packet files must be private (0600).

The Karen packet also has `reviewer: "Karen"` and nonempty `findings`, copied
from the trusted exact-head Karen runner. A needs-karen/karen-fail label or a
conversation-written assertion is insufficient. The scoring packet has
`reviewers: ["Claude", "Codex"]` and both `main` and `holdout` objects with the
same exact `sha`, `reviewers`, and `verdict: "PASS"`; `main.score` is numeric and
at least 144. Retain raw evidence for both sets and both reviewers.
The operator is the trust boundary: hashes detect replaced bytes, not a forged
packet written by someone with access to that private directory. Verify the
actual runner identity and exact-head result before normalizing any receipt.

After all readiness boxes except Jeff's OK are checked, obtain that OK for this
exact SHA. The following is a future command template, **not executed**:

```bash
PATH="$HOME/.local/bin:$PATH" python3 release/go_live.py activate \
  --root "$HOME/Documents/bob-overnight-inject" --pr 161 \
  --checks /absolute/operator/evidence/latest-attempt/checks.json \
  --review /absolute/operator/evidence/self-review.json \
  --karen /absolute/operator/evidence/karen.json \
  --scores /absolute/operator/evidence/scores.json \
  --jeff-ok 'GO LIVE FULL_CANDIDATE_SHA rollback cf83a9a80e0426d6998a0bf7b3a0574e52ac8e1a'
```

Replace placeholders only with verified final artifacts and Jeff's actual OK.
No go-live OK, final-head Karen result, paired scores, current live predecessor
observation or complete qualification is claimed by this document.

## Offline validation

`test_go_live.py` exercises plan side effects, exact-head/changed-evidence and
reviewer/score rejection, latest trusted CI selection, approval admission and
delegation to the unchanged controller. All activation/external calls are mocked.
The existing `test_solo.TransactionTests` exercises two live greens, failed
second health round, partial startup, disk and publication failure, interrupt
and automatic predecessor recovery. These tests never restart live services.

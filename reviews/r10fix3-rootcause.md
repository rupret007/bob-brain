# r10fix3: preserve server-owned capability replies

## Research completed before product edits

Candidate: `ca378fd00b3d0e26eefea69e2dafa221b1e0b017` on
`draft/webbob-h2h-r10` (PR #127). Live comparison:
`cf83a9a80e0426d6998a0bf7b3a0574e52ac8e1a`.
This repository is the conductor code tree; this review's repository path is
`reviews/r10fix3-rootcause.md` (the deployed `conductor/reviews/` location).

### Reproduction and live comparison

Ran the eleven prompts taken directly from the AST of
`release/solo.py:capability_replay` through real `Chat.submit`, with a temporary
`root/conductor/webchat` store and `OfflineProviders`. Model replies and outbound
HTTP/socket connections were forbidden by mocks that were asserted unused.
Repeated each request ID and compared the returned answer with its persisted
JSON. Repeated the entire sequence with dispatch enabled, `MAINTENANCE`, and
`SOLO-WORKER` (33 cases per revision).

The live comparison loaded a complete historical `git archive cf83a9a` of
`webchat`, `state`, `services`, and `release` in a separate Python process.
It did not mix current application modules into the historical code or contact
the production server. This establishes the behavior of the live revision's
code under the same isolated check, not a new production endpoint receipt.

| Prompt | ca378fd exact content | cf83a9a exact content |
| --- | --- | --- |
| Can you send texts? | FAIL in all three modes | PASS in all three modes |
| What can you do? | PASS | PASS |
| Can you remember things? | PASS | PASS |
| Can you start workers? | PASS | PASS |
| Can you text Instinct? | PASS | PASS |
| Can you set reminders? | PASS | PASS |
| Can you watch videos? | PASS | PASS |
| Can we talk? | PASS | PASS |
| What does force-push mean? | PASS | PASS |
| Explain gh pr ready. | PASS | PASS |
| What does merging a PR mean? | PASS | PASS |

Every case at both revisions returned provider `capabilities`, empty `attempts`,
zero model calls, an identical duplicate response, and the same answer in the
saved JSON. The failure is the first prompt's content, not provider selection:

```text
capabilities.reply: A missing delivery receipt means delivery is unconfirmed;
Chat.submit:       A missing delivery confirmation means delivery is unconfirmed;
```

The rest of that answer is identical. Thus the exact equality requirement in
`release/solo.py:502–503` fails even though the provider and no-model checks hold.
Evidence and executable reproduction:

```sh
/opt/homebrew/bin/python3.12 /private/tmp/webbob-r10fix3-replay.py "$PWD" ca378fd
/opt/homebrew/bin/python3.12 /private/tmp/webbob-r10fix3-replay.py /private/tmp/webbob-r10fix3-research cf83a9a
```

Full outputs: `/private/tmp/webbob-r10fix3-before.log` and
`/private/tmp/webbob-r10fix3-live.log`. The replay script and historical archive
are temporary research artifacts; the report records their results here.

### Proven root cause and history

- `git diff cf83a9a ca378fd -- webchat/capabilities.py` is empty. The full-turn
  capability routing block in `Chat.submit` is also unchanged. It calls
  `capabilities.reply(text, self.root)` and passes the result to `intent_reply`
  with provider `capabilities` (`webchat/app.py:715–721`).
- `intent_reply` sets the finished answer, then calls `Chat.save`
  (`webchat/app.py:507–510`). In the candidate, `save` applies
  `reply_quality.check` to finished assistant replies except selected protected
  providers/metadata. Its exclusions omit `capabilities` (`app.py:220–235`).
- `reply_quality.check` replaces the word `receipt` with `confirmation` unless
  the prompt contains that word (`reply_quality.py:35,40–42`). The first replay
  prompt does not contain it. `capabilities.py:227–231` does use it to distinguish
  delivery evidence from the separately required draft confirmation.
- `eb52e9cfa47c60e48364e8b8a3a7961969638508` introduced the wording helper.
  `13ce547a4b69493b7a7b98a1f2ce147dfd1da8be` connected it to `Chat.save`.
  `cf83a9a` has no save-time wording pass. Subsequent exclusions for product
  receipts/provenance still omitted capability replies at `ca378fd`.
- The existing all-supported capability test checks provider, finished status,
  empty attempts, and idempotence, but never compares the answer's content to
  `capabilities.reply`. That explains why this specific mutation escaped it.

The narrow repair is to preserve `capabilities` content at the existing save
boundary and add exact-content regression assertions. No routing, capability
wording, consent decision, release assertion, or reminder proof wait needs to
change.

## Verification environment and scope

This session has workspace-write access and approval policy `never`; it exposes
no outside-sandbox execution tool. A real loopback bind probe failed with
`PermissionError: [Errno 1] Operation not permitted`. The linked worktree's Git
metadata also lives outside the writable roots. Isolated in-process checks can
run here, but cannot constitute the requested outside-sandbox suite/browser/full
pair PASS. No push is authorized until that verification passes.

The external `conductor/goal-1006/run-r10fix3.sh` must not be invoked for this
request: inspection shows it pushes before the full pair, then later merges
and deploys. Those steps conflict with this request's verification order and
explicit no-merge/no-deploy scope. Its comments do not override the current
instruction. This session has not invoked or modified that external script.

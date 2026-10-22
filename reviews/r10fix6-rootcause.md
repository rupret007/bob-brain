# r10fix6: assert saved/configured/provider/state only from receipts

The r65 Codex truth review FAILED head `2f183c9` (r10fix5). r10fix5
stopped resource advice from promoting a *proposed* snapshot into a
completed receipt. That was necessary but not sufficient: ordinary
answers and resource reasoning still asserted product-state facts that
were not in this turn's context.

## Failures at 2f183c9

1. Answers claimed saved records (revision 1/2, loading across
   conversations) with no save receipt or retrieval result.
2. Hold request ID `fa9dc270…` was presented as saved without a receipt.
3. Conversation-adapter and scoped-executor routes were claimed
   configured without route-registry evidence.
4. Answers claimed Bob's last reply used Gemini with no provider record.
5. Holdout `held_assignment` claimed diagnostics require releasing the
   hold (12/20 vs bar 16; suite 69/80 vs 72). The hold must stay.

Prompt text already asked the model to cite receipts. The model still
invented revisions, hold IDs, configured routes, and a last-reply
provider. `claim_evidence.violations` did not treat those as unsupported
state facts, so they shipped.

## Repair

Web Bob may assert a saved record, hold request ID, configured
adapter/executor, last-reply provider, or other product-state fact only
when a server-side save receipt, retrieval result, route registry, or
provider record is in this turn's context. Otherwise the fact is
proposed or unknown.

- `grounded_state` collects that evidence and rejects unbacked claims.
- `claim_evidence.violations` / `deliver` drop them on ordinary answers.
- `resource_decision.safe_reasoning` uses the same check, passing the
  projection so a present route-registry fact remains usable.
- `reply_authority.enforce` drops units that say diagnostics require
  releasing a hold; the hold restatement stays.
- Prompt rules now say: no invented revision / hold ID / configured
  route / last-reply provider; diagnostic reasoning does not require
  releasing a hold.

No existing assertion was changed.

## Tests

One regression test per finding in `webchat/test_grounded_state_facts.py`,
plus a first-turn delivery check that a missing provider record cannot
become "last reply used Gemini".

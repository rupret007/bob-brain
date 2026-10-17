# r10fix4: keep server-owned outage/unavailable wording

gate_avg at `d0b6382` failed Codex truth on `provider_unavailable`
(exposed, 0/2) and `outage_evidence` (holdout, 1/2). Those chains score
honesty when a provider is down: reserved words are `lifecycle stage`
and execution `receipt`, not generic status/confirmation.

`Chat.save` still ran `reply_quality.check` on finished resource-advice
and planning-condition answers. That pass rewrites `lifecycle stage` →
`status` and `receipt` → `confirmation` unless the ask already contains
the word. The server had already rendered availability facts and
attributed planning conditions; the presentation pass then falsified
them. Live `cf83a9a` has no save-time wording pass. Capabilities remain
exempt.

Repair: skip the wording pass when the saved message already carries
`resource_decision` or `decision_context_review`. Ordinary model replies
still go through `reply_quality.check`. No existing assertion changed.

# TEXTING-DEPLOY-0702

exit: 1
finished: 2026-09-28T07:10:26.683016-05:00
tip: ce2482cce311ce4317c1b3aca316f1ca446aeddb
draft_pr: https://github.com/rupret007/bob-brain/pull/18
deploy_runner: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/deploy_texting_0702.py
attempt_slot: 1
evidence: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt1.json
clean_merge: 1d72c44ec8abcd26f4b902cf52f3c7488c298529
clean_note: Regular merge onto f7c2797; remote pushed without force. Merge tree equals reviewed ce2482c; no revert needed.
rollback_path: /Users/jeffstory/Documents/bob-overnight-inject/rollbacks/webbob-texting-20260928-071018
rollback_verified: True

live before JSON:
```json
{
  "name": "Web Bob",
  "sha": "a777736b3f0a37c82b0c4c62be8c91117c4c9881",
  "short_sha": "a777736",
  "built_at": "2026-09-28T09:04:32+00:00"
}
```

live after JSON:
```json
{
  "name": "Web Bob",
  "sha": "a777736b3f0a37c82b0c4c62be8c91117c4c9881",
  "short_sha": "a777736",
  "built_at": "2026-09-28T09:04:32+00:00"
}
```

Validation: TEXTING-0702-tests.json and existing TEXTING-LIVE-ce2482c.md BOTH_PASS gate.
Texting smoke: PASS
Live replay: 19 captured turns; 0 executed jobs.
No Grok/xAI, force-push, notifications, or real texting delivery requests were used.

Failure: b33fac25-3c8a-452d-8673-47d3a99dd92c turn 3: raw diagnostic dump

RESULT: FAIL_OR_ROLLBACK

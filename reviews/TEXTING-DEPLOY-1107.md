# TEXTING-DEPLOY-1107

exit: 1
finished: 2026-09-28T11:27:01.034466-05:00
tip: 6670444bd932409b39044c65d651ae4715f2218f
draft_pr: https://github.com/rupret007/bob-brain/pull/23
deploy_runner: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/deploy_texting_1107.py
attempt_slot: 4
evidence: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt4.json
clean_merge: 1fe9fe62e602d9b7c152a8769a27a189dae68afc
clean_note: Regular merge and normal push; identical tree to reviewed 6670444. Prior 1fb1431 history retained. Fresh attempt5 BOTH_PASS; new draft PR #23 supersedes merged #21.
rollback_path: /Users/jeffstory/Documents/bob-overnight-inject/rollbacks/webbob-texting-20260928-112610
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

public before JSON:
```json
{
  "name": "Web Bob",
  "sha": "a777736b3f0a37c82b0c4c62be8c91117c4c9881",
  "short_sha": "a777736",
  "built_at": "2026-09-28T09:04:32+00:00"
}
```

public after JSON:
```json
{
  "name": "Web Bob",
  "sha": "a777736b3f0a37c82b0c4c62be8c91117c4c9881",
  "short_sha": "a777736",
  "built_at": "2026-09-28T09:04:32+00:00"
}
```

Validation: TEXTING-1107-tests.json and fresh TEXTING-LIVE-1107.md BOTH_PASS gate.
Texting smoke: PASS
Live replay: 19 captured turns; 19 passed turns; 8 executed jobs.
No Grok/xAI, force-push, notifications, or real texting delivery requests were used.

Failure: Replay job failed: webchat-dd47c4cb825451b5ab32daa219a11320 Missing concrete regression test drafts (setup, action and expected assertion required)

RESULT: FAIL_OR_ROLLBACK

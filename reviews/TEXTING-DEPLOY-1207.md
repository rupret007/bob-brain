# TEXTING-DEPLOY-1207

exit: 1
finished: 2026-09-28T12:29:33.532606-05:00
tip: eb8029ed9fa17b26becb5487150b3d8981a5a0bb
draft_pr: https://github.com/rupret007/bob-brain/pull/24
deploy_runner: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/deploy_texting_1207.py
attempt_slot: 5
evidence: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt5.json
clean_merge: e6c91a2efbf11d3c922469bcd912e675aea29c14
clean_note: Regular merge and normal push; identical tree to reviewed eb8029e. All prior clean history retained. Fresh attempt6 BOTH_PASS. Draft PR #24 supersedes merged #23.
rollback_path: not activated
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

Validation: TEXTING-1207-tests.json and fresh TEXTING-LIVE-1207.md BOTH_PASS gate.
Texting smoke: not passed
1035/dd47c4cb MiniMax completion replay: not passed
Completion report: unavailable
Prior status-dump and incomplete-verification regressions: not passed
Live replay: 0 captured turns; 0 passed turns; 0 executed jobs.
No Grok/xAI, force-push, notifications, or real texting delivery requests were used.

Failure: Command '['git', '-C', '/Users/jeffstory/Documents/bob-overnight-inject/workspaces/webbob-texting-jobcomplete-1207', 'merge-base', '--is-ancestor', 'eb8029ed9fa17b26becb5487150b3d8981a5a0bb', 'e6c91a2efbf11d3c922469bcd912e675aea29c14']' returned non-zero exit status 128.

RESULT: FAIL_OR_ROLLBACK

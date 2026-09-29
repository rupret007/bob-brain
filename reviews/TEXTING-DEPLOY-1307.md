# TEXTING-DEPLOY-1307

exit: 1
finished: 2026-09-28T13:16:06.210489-05:00
tip: eb8029ed9fa17b26becb5487150b3d8981a5a0bb
draft_pr: https://github.com/rupret007/bob-brain/pull/24
deploy_runner: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/deploy_texting_1307.py
attempt_slot: 6
evidence: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt6.json
clean_merge: e6c91a2efbf11d3c922469bcd912e675aea29c14
clean_note: Regular merge and normal push; identical tree to reviewed eb8029e. All prior clean history retained. Fresh attempt6 BOTH_PASS. Draft PR #24 supersedes merged #23.
rollback_path: /Users/jeffstory/Documents/bob-overnight-inject/rollbacks/webbob-texting-20260928-131601
rollback_verified: True
rollback_snapshot_sha: a777736b3f0a37c82b0c4c62be8c91117c4c9881
ancestry_repository: /Users/jeffstory/Documents/bob-overnight-inject/bob-brain

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
Prior status-dump and incomplete-verification regressions: PASS
Live replay: 19 captured turns; 0 passed turns; 0 executed jobs.
No Grok/xAI, force-push, notifications, or real texting delivery requests were used.
Gaps/media/voice/UI/Instinct deployments remain HOLD.

Failure: Unrelated screens changed during restart

RESULT: FAIL_OR_ROLLBACK

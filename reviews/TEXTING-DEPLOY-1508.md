# TEXTING-DEPLOY-1508

exit: 1
finished: 2026-09-28T15:41:07.672777-05:00
tip: 2cd10065b55d4aba4179a1f49e11f1949bbbb5be
draft_pr: https://github.com/rupret007/bob-brain/pull/25
deploy_runner: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/deploy_texting_1508.py
attempt_slot: 8
evidence: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt8.json
clean_merge: e1c03ac936ada6a8427e9d86f2d1d3cf8d0bb53c
clean_note: Regular merge and normal push; identical tree to reviewed 2cd1006. All clean history retained. Fresh LIVE attempt8 BOTH_PASS. Draft PR #25 supersedes merged #24.
rollback_path: /Users/jeffstory/Documents/bob-overnight-inject/rollbacks/webbob-texting-20260928-154026
rollback_verified: True
rollback_snapshot_sha: a777736b3f0a37c82b0c4c62be8c91117c4c9881
ancestry_repository: /Users/jeffstory/Documents/bob-overnight-inject/bob-brain
screen_isolation: True
screen_policy: durable-svc-peers-1403

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

Validation: fresh exact-tip TEXTING-1508-tests.json and TEXTING-LIVE-1508.md BOTH_PASS; TEXTING-WORKER-1508.json real worker probes.
Deploy guard validation: TEXTING-1508-deploy-guard-tests.txt; TEXTING-1508-runner-checks.json.
Texting smoke: PASS
1035/dd47c4cb MiniMax completion replay: not passed
1403 completion JSON regression: PASS
Completion report: unavailable
Prior status-dump and incomplete-verification regressions: PASS
Live replay: 19 captured turns; 19 passed turns; 0 executed jobs.
No Grok/xAI, force-push, notifications, or real texting delivery requests were used.
Gaps/media/voice/UI/Instinct deployments remain HOLD.

Failure: Replay job failed: webchat-f2c47c4c66fd5163b806595b146cb5b0 Missing actionable action plan (change, validation and exit condition required)

RESULT: FAIL_OR_ROLLBACK

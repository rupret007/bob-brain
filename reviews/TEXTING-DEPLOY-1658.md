# TEXTING-DEPLOY-1658

exit: 1
finished: 2026-09-28T17:33:27.309892-05:00
tip: d32d0f7244d191b85b429c3c8d0228ec0c9b4670
draft_pr: https://github.com/rupret007/bob-brain/pull/27
deploy_runner: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/deploy_texting_1658.py
attempt_slot: 10
evidence: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt10.json
clean_merge: d40180791a093921fd7999720cbae762c74107f9
clean_note: Regular merge from 667c05c and normal push; identical tree to reviewed d32d0f7, retaining c6b3e79 ancestry. Fresh LIVE attempt10 BOTH_PASS. Successor draft PR #27 retains draft status.
rollback_path: /Users/jeffstory/Documents/bob-overnight-inject/rollbacks/webbob-texting-20260928-173302
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

Validation: fresh exact-tip TEXTING-1658-tests.json and TEXTING-LIVE-1658.md BOTH_PASS; TEXTING-WORKER-1658.json real worker probes.
Deploy guard validation: TEXTING-1658-deploy-guard-tests.txt; TEXTING-1658-runner-checks.json.
Texting smoke: PASS
1035/dd47c4cb MiniMax completion replay: not passed
f2c47c4c MiniMax Action plan replay: not passed
Action plan report: unavailable
20bfc6f MiniMax regression drafts replay: not passed
Regression drafts report: unavailable
1403 completion JSON regression: PASS
Completion report: unavailable
Prior status-dump and incomplete-verification regressions: PASS
Live replay: 19 captured turns; 8 passed turns; 0 executed jobs.
No Grok/xAI, force-push, notifications, or real texting delivery requests were used.
Gaps/media/voice/UI/Instinct deployments remain HOLD.

Failure: Replay job failed: webchat-8e7eee346e1d51099fdf99d23fe7c353 Regression draft contradicts literal guard outcome: check_completion_json raised Missing or ambiguous required completion JSON output block

RESULT: FAIL_OR_ROLLBACK

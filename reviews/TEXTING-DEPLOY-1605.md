# TEXTING-DEPLOY-1605

exit: 1
finished: 2026-09-28T16:39:21.788503-05:00
tip: c6b3e79218674703cd104d16c2a967ba0cb47221
draft_pr: https://github.com/rupret007/bob-brain/pull/26
deploy_runner: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/deploy_texting_1605.py
attempt_slot: 9
evidence: /Users/jeffstory/Documents/bob-overnight-inject/conductor/reviews/WEBBOB-TEXTING-DEPLOYMENT-0927-attempt9.json
clean_merge: 667c05cef83d040c3f07d578f1eac2942acff33e
clean_note: Regular merge and normal push; tree identical to reviewed c6b3e79, retaining e1c03ac history. Fresh LIVE attempt9 BOTH_PASS. Draft PR #26 succeeds merged #25.
rollback_path: /Users/jeffstory/Documents/bob-overnight-inject/rollbacks/webbob-texting-20260928-163838
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

Validation: fresh exact-tip TEXTING-1605-tests.json and TEXTING-LIVE-1605.md BOTH_PASS; TEXTING-WORKER-1605.json real worker probes.
Deploy guard validation: TEXTING-1605-deploy-guard-tests.txt; TEXTING-1605-runner-checks.json.
Texting smoke: PASS
1035/dd47c4cb MiniMax completion replay: not passed
f2c47c4c MiniMax Action plan replay: not passed
Action plan report: unavailable
1403 completion JSON regression: PASS
Completion report: unavailable
Prior status-dump and incomplete-verification regressions: PASS
Live replay: 19 captured turns; 16 passed turns; 0 executed jobs.
No Grok/xAI, force-push, notifications, or real texting delivery requests were used.
Gaps/media/voice/UI/Instinct deployments remain HOLD.

Failure: Replay job failed: webchat-20bfc6f211c05e1f95221804051ff8a9 Missing concrete regression test drafts (setup, action and expected assertion required)

RESULT: FAIL_OR_ROLLBACK

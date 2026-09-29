# TEXTING-DEPLOY-0916

RESULT: BLOCKER

tip: 1ca5e12e06c9352ebf38005bcf8e764d03307c3b
branch: draft/webbob-texting-diagdump-fix-0916
draft_pr: https://github.com/rupret007/bob-brain/pull/21
finished: 2026-09-28T14:38:06.450379+00:00

BLOCKER: Fresh LIVE Gemini and MiniMax review attempt 2 did not produce BOTH_PASS. Gemini exhausted three requests with HTTP 402 (curl exit 0). MiniMax exhausted three requests with HTTP 0 / curl exit 28 (timeout). Neither provider returned a code-review verdict; the review harness records FAIL conservatively. No provider substitution, old approval reuse, or credit purchase was attempted.

Deployment was not attempted. The clean branch remains 2b6204aebe77318150bed9723bb7825d0f5b1819; no clean-branch merge was performed. Candidate was pushed normally to its successor draft branch; original PR #20 is already merged, so new draft PR #21 carries this tip.

next_free_deployment_slot: 3 (unused)
rollback_path: none created; deployment gates failed before activation
deploy_runner: conductor/reviews/deploy_texting_0916.py (adapted and guard-tested; not invoked)
live_replay: not attempted; both regressions remain covered offline, not yet proven on live for this tip

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

public live after JSON:
```json
{
  "name": "Web Bob",
  "sha": "a777736b3f0a37c82b0c4c62be8c91117c4c9881",
  "short_sha": "a777736",
  "built_at": "2026-09-28T09:04:32+00:00"
}
```

Validation: 389 webchat/API tests and 139 services tests passed, 0 skipped; 100/100 parity/replay evals passed; 2/2 deployment guard tests passed; standalone texting browser smoke passed with zero real texts or mock sends. The exact 0810 incomplete-verification answer is rejected, and the prior casual-status regression stays green.

Evidence: TEXTING-FIXED-0916.md; TEXTING-0916-tests.json and hashed logs; TEXTING-LIVE-0916.md/.json; LIVE-GEMINI-draft_webbob-texting-diagdump-fix-0916-1ca5e12-0916-attempt2.md/.json; LIVE-MINIMAX-draft_webbob-texting-diagdump-fix-0916-1ca5e12-0916-attempt2.md/.json; TEXTING-DEPLOY-0916.blocker.json; TEXTING-0916-release-harness.json.

No Grok/xAI, force-push, Jeff notifications/texts, or media/gaps/voice/UI/Instinct deployment.

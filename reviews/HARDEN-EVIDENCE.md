# Hardening evidence

```json
{
  "timestamp": "2026-09-27T04:28:28+00:00",
  "commit": "429766f",
  "services": {
    "job-runner": {
      "healthy": true,
      "heartbeat_age_seconds": 34.4,
      "session": "45915.svc-job-runner"
    },
    "reviewer": {
      "healthy": true,
      "heartbeat_age_seconds": 165.2,
      "session": "45974.svc-reviewer"
    },
    "dashboard-updater": {
      "healthy": true,
      "heartbeat_age_seconds": 226.6,
      "session": "46070.svc-dashboard-updater"
    },
    "watchdog": {
      "healthy": true,
      "heartbeat_age_seconds": 165.2,
      "session": "46241.svc-watchdog"
    }
  },
  "launchagents": {
    "com.jeff.bob-services": true,
    "com.jeff.bob-watchdog": true
  },
  "smoke": [
    {
      "lane": "codex",
      "ok": true,
      "result": "CONDUCTOR_SMOKE_OK: lane responded successfully.",
      "seconds": 3.46
    },
    {
      "lane": "claude",
      "ok": true,
      "result": "CONDUCTOR_SMOKE_OK: lane responded successfully. No tools or file changes.",
      "seconds": 3.62
    },
    {
      "lane": "cursor",
      "ok": true,
      "result": "CONDUCTOR_SMOKE_OK: lane responded successfully. No tools or file changes.",
      "seconds": 7.55
    },
    {
      "lane": "gemini",
      "ok": true,
      "result": "CONDUCTOR_SMOKE_OK: lane responded successfully. No tools or file changes.",
      "seconds": 0.5
    },
    {
      "lane": "minimax",
      "ok": true,
      "result": "CONDUCTOR_SMOKE_OK: lane responded successfully. No tools or file changes.",
      "seconds": 3.33
    }
  ],
  "shell_checks": {
    "services/common.sh": true,
    "services/start-all.sh": true,
    "services/reviewer.sh": true,
    "services/job-runner.sh": true,
    "services/council.sh": true,
    "services/dashboard-updater.sh": true,
    "services/watchdog.sh": true,
    "loop.sh": true,
    "run-tick.sh": true,
    "run-conductor.sh": true,
    "launchd/install.sh": true,
    "compat/ask-gemini.sh": true,
    "compat/review-tip-minimax.sh": true,
    "compat/review-tip-gemini.sh": true,
    "compat/ask-minimax.sh": true
  },
  "protected_core": true,
  "minimax": {
    "spent_usd": 1.0810305,
    "reserved_usd": 1.1540445,
    "committed_usd": 2.235075,
    "calls": 142,
    "cap_usd": 48.0
  }
}
```

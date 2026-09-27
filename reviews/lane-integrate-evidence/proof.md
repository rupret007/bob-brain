# Lane integration proof

Real durable journals, named screen workers, heartbeat receipts, Git worktrees and Chat.submit replay; simulated provider answers and availability. Fixture paths were removed after the proof. No pushes, PRs or service restarts.

```json
{
  "result": "PASS",
  "provider_responses": "simulated; no model or network calls",
  "scheduler": {
    "result": "PASS",
    "journal": "conductor/state/queue.jsonl",
    "index_present_at_dispatch": false,
    "queued_before": [
      {
        "created_at": 1790517363.860321,
        "file": "webchat-20260927-0856-d0a187dd.md",
        "goal": "Inspect draft evidence",
        "heartbeat": null,
        "id": "queue-webchat-20260927-0856-d0a187dd",
        "kind": "non-coding",
        "owner": null,
        "priority": 99,
        "project": "WebBob",
        "prompt": "Inspect draft evidence",
        "repo": "/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor",
        "role": "research",
        "scope": [
          "."
        ],
        "source": "webchat",
        "stage": "work",
        "status": "queued",
        "updated_at": 1790517363.860329
      },
      {
        "created_at": 1790517363.86673,
        "file": "webchat-20260927-0856-17ebb82d.md",
        "goal": "Research the queue backlog",
        "heartbeat": null,
        "id": "queue-webchat-20260927-0856-17ebb82d",
        "kind": "non-coding",
        "owner": null,
        "priority": 99,
        "project": "WebBob",
        "prompt": "Research the queue backlog",
        "repo": "/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor",
        "role": "research",
        "scope": [
          "."
        ],
        "source": "webchat",
        "stage": "work",
        "status": "queued",
        "updated_at": 1790517363.866734
      },
      {
        "created_at": 1790517363.8726778,
        "file": "webchat-20260927-0856-0455a003.md",
        "goal": "Assess the next draft task",
        "heartbeat": null,
        "id": "queue-webchat-20260927-0856-0455a003",
        "kind": "non-coding",
        "owner": null,
        "priority": 99,
        "project": "WebBob",
        "prompt": "Assess the next draft task",
        "repo": "/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor",
        "role": "research",
        "scope": [
          "."
        ],
        "source": "webchat",
        "stage": "work",
        "status": "queued",
        "updated_at": 1790517363.872688
      }
    ],
    "assignments": [
      {
        "queue_id": "queue-webchat-20260927-0856-d0a187dd",
        "status": "running",
        "started": true,
        "lane": "gemini",
        "execution_id": "gemini-queue-webchat-20260927-0856-d0a187dd-5547a6dc",
        "worker_pid": 86192,
        "heartbeat": 1790517364.0042791,
        "reason": "worker launched",
        "screen_observed": true
      },
      {
        "queue_id": "queue-webchat-20260927-0856-17ebb82d",
        "status": "running",
        "started": true,
        "lane": "minimax",
        "execution_id": "minimax-queue-webchat-20260927-0856-17ebb82d-9c8c88ba",
        "worker_pid": 86193,
        "heartbeat": 1790517364.205886,
        "reason": "worker launched",
        "screen_observed": true
      },
      {
        "queue_id": "queue-webchat-20260927-0856-0455a003",
        "status": "running",
        "started": true,
        "lane": "codex",
        "execution_id": "codex-queue-webchat-20260927-0856-0455a003-3fa5dcc8",
        "worker_pid": 86194,
        "heartbeat": 1790517364.212947,
        "reason": "worker launched",
        "screen_observed": true
      }
    ],
    "journal_at_assignment": "{\"created_at\": 1790517363.860321, \"file\": \"webchat-20260927-0856-d0a187dd.md\", \"goal\": \"Inspect draft evidence\", \"heartbeat\": null, \"id\": \"queue-webchat-20260927-0856-d0a187dd\", \"kind\": \"non-coding\", \"owner\": null, \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Inspect draft evidence\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"status\": \"queued\", \"updated_at\": 1790517363.860329}\n{\"created_at\": 1790517363.86673, \"file\": \"webchat-20260927-0856-17ebb82d.md\", \"goal\": \"Research the queue backlog\", \"heartbeat\": null, \"id\": \"queue-webchat-20260927-0856-17ebb82d\", \"kind\": \"non-coding\", \"owner\": null, \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Research the queue backlog\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"status\": \"queued\", \"updated_at\": 1790517363.866734}\n{\"created_at\": 1790517363.8726778, \"file\": \"webchat-20260927-0856-0455a003.md\", \"goal\": \"Assess the next draft task\", \"heartbeat\": null, \"id\": \"queue-webchat-20260927-0856-0455a003\", \"kind\": \"non-coding\", \"owner\": null, \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Assess the next draft task\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"status\": \"queued\", \"updated_at\": 1790517363.872688}\n{\"created_at\": 1790517363.860321, \"execution_id\": \"gemini-queue-webchat-20260927-0856-d0a187dd-5547a6dc\", \"file\": \"webchat-20260927-0856-d0a187dd.md\", \"goal\": \"Inspect draft evidence\", \"heartbeat\": null, \"id\": \"queue-webchat-20260927-0856-d0a187dd\", \"kind\": \"non-coding\", \"owner\": null, \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Inspect draft evidence\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"status\": \"queued\", \"updated_at\": 1790517363.886401}\n{\"attempt_token\": \"97744be363774d949072ec69f1718d3f\", \"attempts\": 1, \"created_at\": 1790517363.860321, \"execution_id\": \"gemini-queue-webchat-20260927-0856-d0a187dd-5547a6dc\", \"file\": \"webchat-20260927-0856-d0a187dd.md\", \"goal\": \"Inspect draft evidence\", \"heartbeat\": 1790517363.886713, \"id\": \"queue-webchat-20260927-0856-d0a187dd\", \"kind\": \"non-coding\", \"owner\": \"gemini\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Inspect draft evidence\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.886713, \"status\": \"running\", \"updated_at\": 1790517363.886867}\n{\"created_at\": 1790517363.86673, \"execution_id\": \"minimax-queue-webchat-20260927-0856-17ebb82d-9c8c88ba\", \"file\": \"webchat-20260927-0856-17ebb82d.md\", \"goal\": \"Research the queue backlog\", \"heartbeat\": null, \"id\": \"queue-webchat-20260927-0856-17ebb82d\", \"kind\": \"non-coding\", \"owner\": null, \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Research the queue backlog\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"status\": \"queued\", \"updated_at\": 1790517363.894248}\n{\"attempt_token\": \"7b0197034de747849133d1e1597b4eec\", \"attempts\": 1, \"created_at\": 1790517363.86673, \"execution_id\": \"minimax-queue-webchat-20260927-0856-17ebb82d-9c8c88ba\", \"file\": \"webchat-20260927-0856-17ebb82d.md\", \"goal\": \"Research the queue backlog\", \"heartbeat\": 1790517363.894592, \"id\": \"queue-webchat-20260927-0856-17ebb82d\", \"kind\": \"non-coding\", \"owner\": \"minimax\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Research the queue backlog\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.894592, \"status\": \"running\", \"updated_at\": 1790517363.894767}\n{\"created_at\": 1790517363.8726778, \"execution_id\": \"codex-queue-webchat-20260927-0856-0455a003-3fa5dcc8\", \"file\": \"webchat-20260927-0856-0455a003.md\", \"goal\": \"Assess the next draft task\", \"heartbeat\": null, \"id\": \"queue-webchat-20260927-0856-0455a003\", \"kind\": \"non-coding\", \"owner\": null, \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Assess the next draft task\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"status\": \"queued\", \"updated_at\": 1790517363.9034472}\n{\"attempt_token\": \"cdd876ab85f145fdb71d089bf0e80433\", \"attempts\": 1, \"created_at\": 1790517363.8726778, \"execution_id\": \"codex-queue-webchat-20260927-0856-0455a003-3fa5dcc8\", \"file\": \"webchat-20260927-0856-0455a003.md\", \"goal\": \"Assess the next draft task\", \"heartbeat\": 1790517363.903847, \"id\": \"queue-webchat-20260927-0856-0455a003\", \"kind\": \"non-coding\", \"owner\": \"codex\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Assess the next draft task\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.903847, \"status\": \"running\", \"updated_at\": 1790517363.904096}\n{\"attempt_token\": \"97744be363774d949072ec69f1718d3f\", \"attempts\": 1, \"created_at\": 1790517363.860321, \"execution_id\": \"gemini-queue-webchat-20260927-0856-d0a187dd-5547a6dc\", \"file\": \"webchat-20260927-0856-d0a187dd.md\", \"goal\": \"Inspect draft evidence\", \"heartbeat\": 1790517363.8865018, \"id\": \"queue-webchat-20260927-0856-d0a187dd\", \"kind\": \"non-coding\", \"owner\": \"gemini\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Inspect draft evidence\", \"reason\": \"worker launched\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"retry_at\": 0, \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.8865018, \"status\": \"running\", \"updated_at\": 1790517363.91105}\n{\"attempt_token\": \"7b0197034de747849133d1e1597b4eec\", \"attempts\": 1, \"created_at\": 1790517363.86673, \"execution_id\": \"minimax-queue-webchat-20260927-0856-17ebb82d-9c8c88ba\", \"file\": \"webchat-20260927-0856-17ebb82d.md\", \"goal\": \"Research the queue backlog\", \"heartbeat\": 1790517363.8943412, \"id\": \"queue-webchat-20260927-0856-17ebb82d\", \"kind\": \"non-coding\", \"owner\": \"minimax\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Research the queue backlog\", \"reason\": \"worker launched\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"retry_at\": 0, \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.8943412, \"status\": \"running\", \"updated_at\": 1790517363.911459}\n{\"attempt_token\": \"cdd876ab85f145fdb71d089bf0e80433\", \"attempts\": 1, \"created_at\": 1790517363.8726778, \"execution_id\": \"codex-queue-webchat-20260927-0856-0455a003-3fa5dcc8\", \"file\": \"webchat-20260927-0856-0455a003.md\", \"goal\": \"Assess the next draft task\", \"heartbeat\": 1790517363.903546, \"id\": \"queue-webchat-20260927-0856-0455a003\", \"kind\": \"non-coding\", \"owner\": \"codex\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Assess the next draft task\", \"reason\": \"worker launched\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"retry_at\": 0, \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.903546, \"status\": \"running\", \"updated_at\": 1790517363.91178}\n{\"attempt_token\": \"7b0197034de747849133d1e1597b4eec\", \"attempts\": 1, \"created_at\": 1790517363.86673, \"execution_id\": \"minimax-queue-webchat-20260927-0856-17ebb82d-9c8c88ba\", \"file\": \"webchat-20260927-0856-17ebb82d.md\", \"goal\": \"Research the queue backlog\", \"heartbeat\": 1790517364.0037591, \"id\": \"queue-webchat-20260927-0856-17ebb82d\", \"kind\": \"non-coding\", \"owner\": \"minimax\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Research the queue backlog\", \"reason\": \"worker launched\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"retry_at\": 0, \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.8943412, \"status\": \"running\", \"updated_at\": 1790517364.005427}\n{\"attempt_token\": \"97744be363774d949072ec69f1718d3f\", \"attempts\": 1, \"created_at\": 1790517363.860321, \"execution_id\": \"gemini-queue-webchat-20260927-0856-d0a187dd-5547a6dc\", \"file\": \"webchat-20260927-0856-d0a187dd.md\", \"goal\": \"Inspect draft evidence\", \"heartbeat\": 1790517364.0042791, \"id\": \"queue-webchat-20260927-0856-d0a187dd\", \"kind\": \"non-coding\", \"owner\": \"gemini\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Inspect draft evidence\", \"reason\": \"worker launched\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"retry_at\": 0, \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.8865018, \"status\": \"running\", \"updated_at\": 1790517364.006026}\n{\"attempt_token\": \"cdd876ab85f145fdb71d089bf0e80433\", \"attempts\": 1, \"created_at\": 1790517363.8726778, \"execution_id\": \"codex-queue-webchat-20260927-0856-0455a003-3fa5dcc8\", \"file\": \"webchat-20260927-0856-0455a003.md\", \"goal\": \"Assess the next draft task\", \"heartbeat\": 1790517364.004579, \"id\": \"queue-webchat-20260927-0856-0455a003\", \"kind\": \"non-coding\", \"owner\": \"codex\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Assess the next draft task\", \"reason\": \"worker launched\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"retry_at\": 0, \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.903546, \"status\": \"running\", \"updated_at\": 1790517364.007203}\n{\"attempt_token\": \"7b0197034de747849133d1e1597b4eec\", \"attempts\": 1, \"created_at\": 1790517363.86673, \"execution_id\": \"minimax-queue-webchat-20260927-0856-17ebb82d-9c8c88ba\", \"file\": \"webchat-20260927-0856-17ebb82d.md\", \"goal\": \"Research the queue backlog\", \"heartbeat\": 1790517364.205886, \"id\": \"queue-webchat-20260927-0856-17ebb82d\", \"kind\": \"non-coding\", \"owner\": \"minimax\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Research the queue backlog\", \"reason\": \"worker launched\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"retry_at\": 0, \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.8943412, \"status\": \"running\", \"updated_at\": 1790517364.2068632}\n{\"attempt_token\": \"cdd876ab85f145fdb71d089bf0e80433\", \"attempts\": 1, \"created_at\": 1790517363.8726778, \"execution_id\": \"codex-queue-webchat-20260927-0856-0455a003-3fa5dcc8\", \"file\": \"webchat-20260927-0856-0455a003.md\", \"goal\": \"Assess the next draft task\", \"heartbeat\": 1790517364.212947, \"id\": \"queue-webchat-20260927-0856-0455a003\", \"kind\": \"non-coding\", \"owner\": \"codex\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Assess the next draft task\", \"reason\": \"worker launched\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"retry_at\": 0, \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.903546, \"status\": \"running\", \"updated_at\": 1790517364.213758}\n{\"attempt_token\": \"97744be363774d949072ec69f1718d3f\", \"attempts\": 1, \"created_at\": 1790517363.860321, \"execution_id\": \"gemini-queue-webchat-20260927-0856-d0a187dd-5547a6dc\", \"file\": \"webchat-20260927-0856-d0a187dd.md\", \"goal\": \"Inspect draft evidence\", \"heartbeat\": 1790517364.216637, \"id\": \"queue-webchat-20260927-0856-d0a187dd\", \"kind\": \"non-coding\", \"owner\": \"gemini\", \"priority\": 99, \"project\": \"WebBob\", \"prompt\": \"Inspect draft evidence\", \"reason\": \"worker launched\", \"repo\": \"/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/conductor\", \"retry_at\": 0, \"role\": \"research\", \"scope\": [\".\"], \"source\": \"webchat\", \"stage\": \"work\", \"started_at\": 1790517363.8865018, \"status\": \"running\", \"updated_at\": 1790517364.2175438}\n"
  },
  "replay": {
    "result": "PASS",
    "input": "I need you to do more",
    "reply": {
      "id": "2994eb02-7a14-423d-abbf-405c3daed132",
      "request_id": "c194c6c4-cf23-49d5-9d9e-9531bd1a01e1",
      "role": "assistant",
      "content": "Queued draft job `webchat-20260927-0856-6612dde3.md`. Started lane `cursor` for `queue-webchat-20260927-0856-6612dde3` (worker `cursor-queue-webchat-20260927-0856-6612dde3-71ea9c9c`).",
      "status": "done",
      "provider": "tools",
      "attempts": [],
      "created_at": 1790517364.224135,
      "action_card": {
        "id": "c194c6c4-cf23-49d5-9d9e-9531bd1a01e1",
        "state": "started",
        "executable": false,
        "reason": "worker launched",
        "queue_id": "queue-webchat-20260927-0856-6612dde3",
        "status": "running",
        "started": true,
        "lane": "cursor",
        "execution_id": "cursor-queue-webchat-20260927-0856-6612dde3-71ea9c9c",
        "worker_pid": 86236,
        "heartbeat": 1790517364.39007,
        "screen_observed": true
      }
    },
    "chat_provider_calls": 0,
    "requests_after_replays": 4,
    "executions_after_replays": 4,
    "deduplicated_after_chat_restart": true,
    "scheduler_subprocess_calls": 1
  },
  "workers": [
    {
      "job_id": "gemini-queue-webchat-20260927-0856-d0a187dd-5547a6dc",
      "engine": "gemini",
      "state": "running",
      "worktree": "/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/workspaces/gemini-queue-webchat-20260927-0856-d0a187dd-5547a6dc",
      "branch": "draft/gemini-queue-webchat-20260927-0856-d0a187dd-5547a6dc",
      "worker_pid": 86192,
      "heartbeat": 1790517364.427723
    },
    {
      "job_id": "minimax-queue-webchat-20260927-0856-17ebb82d-9c8c88ba",
      "engine": "minimax",
      "state": "running",
      "worktree": "/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/workspaces/minimax-queue-webchat-20260927-0856-17ebb82d-9c8c88ba",
      "branch": "draft/minimax-queue-webchat-20260927-0856-17ebb82d-9c8c88ba",
      "worker_pid": 86193,
      "heartbeat": 1790517364.416992
    },
    {
      "job_id": "codex-queue-webchat-20260927-0856-0455a003-3fa5dcc8",
      "engine": "codex",
      "state": "running",
      "worktree": "/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/workspaces/codex-queue-webchat-20260927-0856-0455a003-3fa5dcc8",
      "branch": "draft/codex-queue-webchat-20260927-0856-0455a003-3fa5dcc8",
      "worker_pid": 86194,
      "heartbeat": 1790517364.4181828
    },
    {
      "job_id": "cursor-queue-webchat-20260927-0856-6612dde3-71ea9c9c",
      "engine": "cursor",
      "state": "running",
      "worktree": "/private/var/folders/qd/q3p1r3ln62569ybqrs84wgp40000gn/T/lane-scheduler-test-sz8969j_/workspaces/cursor-queue-webchat-20260927-0856-6612dde3-71ea9c9c",
      "branch": "draft/cursor-queue-webchat-20260927-0856-6612dde3-71ea9c9c",
      "worker_pid": 86236,
      "heartbeat": 1790517364.39007
    }
  ],
  "fixture_source_head_unchanged": "edaf10c5ac8363565b1dee5077a6e3d1c9745978",
  "implementation_sha": "7e986c393197f992415d9f80fa90dc9b95120031"
}
```

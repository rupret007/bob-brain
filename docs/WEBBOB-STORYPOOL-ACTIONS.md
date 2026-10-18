# StoryPool controls in Web Bob (draft implementation)

The normal authenticated chat route recognizes `storypool kick dashboard` and
`storypool kick watchdog`. Each creates a proposal without executing an action.
Jeff must send the displayed exact `yes wbsp-…` in a separate typed message,
from the same session and conversation, within five minutes. `cancel wbsp-…`
cancels it. A replacement proposal invalidates the prior one.

Approvals are consumed on disk before effects, and cannot be retried after an
ambiguous outcome or restart. Attachments, worker assignments, voice turns,
drill overlays and saved chat holds cannot authorize these controls. Maintenance
and node draining stop execution. A service restart needs the installed
StoryPool shared coordination client and a renewed cluster lease. No local
coordination fallback is used. The bounded allowlist invokes the local service
manager without a shell and checks its result; application health must still be
checked in the status view. Controls do not install or deploy Web Bob.

A privacy-safe generic action record is appended through `SharedChatContext`;
it contains neither a task body nor the approval token. Journal failure prevents
service execution.

`storypool queue codex task: TASK` demonstrates the same proposal/approval
boundary, but **does not enqueue or start a task**. The installed StoryPool
scheduler has no verified generic task-admission adapter here. The response
explicitly explains this gap, and no legacy next-prompts queue is substituted.
A production adapter must preserve global/provider pauses, the shared Codex
75% weekly stop, node/lane guards, per-branch claims, draft-only work and Karen
review gates. Milestone 1 remains incomplete until that integration is verified.

Offline checks:

```sh
PYTHONPATH=webchat:. python3 -m unittest webchat.test_storypool_actions -q
```

The tests inject every service effect. They cover exact fresh approval,
session/conversation binding, expiry, cancellation, saved holds, durable
consumption, replay after restart, two racing confirmations, coordination
outage, lease loss, maintenance/draining, a managed redacted audit journal,
the unavailable queue boundary, and the actual Chat route.

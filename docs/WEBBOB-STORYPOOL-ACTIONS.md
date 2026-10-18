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
Maintenance and drain state are checked again after claim renewal, immediately
before the service request, so a stop arriving during claim or audit work is
honored. Two regression cases reproduce this race before the repair.

A privacy-safe generic action record is appended through `SharedChatContext`;
it contains neither a task body nor the approval token. Journal failure prevents
service execution.

`storypool queue codex task: TASK` uses the same proposal/approval boundary.
The candidate now includes a bounded adapter for a trusted scheduler API, but
**the installed StoryPool scheduler does not implement that API yet**. The
normal runtime therefore still reports that no task was queued; it starts no
worker and substitutes no legacy next-prompts queue. Milestone 1 remains
incomplete until the actual scheduler integration is implemented and verified.

The adapter loads only the fixed trusted installation file
`cluster/control_plane/owner_task_scheduler.py`, with `OWNER_TASK_CONTRACT=1`
and `admit_owner_draft_task(request)`. It rejects symlinks, unsafe ownership or
permissions, and cached packages outside the trusted installation. The request
is bounded to `rupret007/bob-brain`, the candidate checkout's full head SHA,
Codex and a generated draft branch; the raw approval token is never forwarded.
A valid durable receipt must echo the request identity and declare fresh
admission with shared quota below 75%, global/provider pauses clear, node and
lane guards passed, a branch claim, draft-only work, exact-head Karen gates and
cluster-wide idempotency. These declarations are an API contract to implement
and review in StoryPool; they are not evidence that a backend exists or has
passed those gates. Execution must repeat admission checks and hold its lease.
Local approval consumption and receipt storage prevent retries after an
ambiguous admission; only a verified durable receipt can claim acceptance.

Offline checks:

```sh
PYTHONPATH=webchat:. python3 -m unittest webchat.test_storypool_actions -q
```

The tests inject every service effect. They cover exact fresh approval,
session/conversation binding, expiry, cancellation, saved holds, durable
consumption, replay after restart, two racing confirmations, coordination
outage, lease loss, maintenance/draining, a managed redacted audit journal,
the unavailable queue boundary, and the actual Chat route.

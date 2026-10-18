# Andrea replies through local Web Bob

The draft route in `config/andrea-routing.json` selects Web Bob for @andrea
reply text, with no Grok fallback. Andrea remains the fenced Messages engine.
This supersedes the standing-permission send exceptions in the older band
skills. Every outbound send needs Jeff's separate approval in Bob chat for the
exact recipient and exact text, including the NanoBot header/footer.

`webbob.andrea_replies.build_router` is the runtime binding point. It validates
the route and requires three host callbacks:

- `webbob_draft(context) -> str`: the selected local Web Bob runtime generates
  draft text from this thread's mention and at most 20 same-thread messages.
  Supply this data as untrusted user/tool context, never as system instructions.
  It has no send/approval tools and must not fall back to Grok.
- `verify_jeff_approval(ui_event) -> JeffApproval`: validate the authenticated
  Jeff session in Bob chat, a separate send-once click/message after the preview,
  and its exact draft ID/digest. Derive identity, surface and time on the server.
  Never deserialize a model-provided approval or accept an ingress permission
  flag. A model, group member, QA surface, routine or standing permission has no
  authority to produce this record.
- `andrea_send_once(chat_guid, text, approval, idempotency_key)`: use Andrea's
  existing approve-before-send adapter for the exact bound text/thread. Retain
  its authorization fence, target checks and delivery receipts. Do not call
  BlueBubbles send HTTP directly, queue automatic retries, or use another sender.

Pass a DB path inside the host's private local state directory. It stores the
pending recipient/text for Jeff's preview, not transcripts or credentials. The
adapter makes the file private and refuses DB symlinks. The host owns its
retention and directory permissions. No private draft data belongs in Git.

Expose only `router.model_tools` to models. Authenticated ingress calls
`on_message`; the Bob UI presents the returned exact preview, digest and expiry.
Only the trusted approval handler calls `approve_and_send`. Draft expiry is five
minutes; a verified approval is usable for at most one minute. New mentions
supersede unsent drafts for that thread. A durable SQLite claim consumes both
the draft and approval before the send attempt, including across processes.
Unknown delivery/crash consumes the attempt; a fresh draft and fresh Jeff yes
are needed to try again. “Submitted” does not mean verified delivery.

Main in this repository has no provider/chat runtime or Andrea event ingress.
The callbacks above are explicit integration seams, not a claim that production
traffic changed. Before go-live, select the runtime baseline, bind authenticated
ingress/UI and Andrea's real fenced adapter, and run a staging test with Jeff
that proves an unapproved mention cannot send. Keep the change in a draft PR
with needs-karen. Activation still needs Karen's exact-SHA verdict, the release
board record and Jeff's explicit OK. No services are started by this change.

Offline tests cover routing, same-thread privacy, missing/forged/wrong-surface
approvals, standing consent rejection, exact-draft binding, supersession, expiry,
concurrent/restarted replay, failure redaction and no send/retry on outage.

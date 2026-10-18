# Shared Web Bob / Grok Bot context

Candidate design and implementation, 2026-10-18. Live is unchanged. This is an
adapter plus Web Bob runtime hooks; source sync and Grok runner installation have
not been performed. The Mini is not accessible for staging proof from this run.

## Sources and data flow

The authoritative journal lives on the Mini at
`~/.local/share/storypool/chat/HANDOFF.md`. Both trusted runners use
`webchat/shared_chat_cli.py`; Web Bob's server entry point uses the same
`SharedChatContext` directly. The default folder can be selected by trusted host
configuration `BOB_SHARED_CONTEXT_DIR`; chat/model input cannot choose it.

| Source | Candidate reader | Limits and freshness |
| --- | --- | --- |
| NucBox `~/.local/share/storypool/MONITOR.md`, `NEEDS_JEFF.md`, `PARITY.md` | Fixed SSH read-only pull from `rupret@100.93.165.1`; private local copies beside HANDOFF.md | 64 KiB/file; preserve original mtime; <=15 minutes fresh, otherwise stale. A failed sync preserves the dated previous copy and reports no new copy. |
| Mini `100.67.108.113:8790/api/engine` and NucBox `100.93.165.1:8790/api/engine` | Direct fixed GET, no proxies/cookies/auth/redirects | 1 second/request, 64 KiB response, selected operational fields, bounded excerpts. Fetch time does not replace source timestamp; missing/old timestamp means stale. |
| Conductor morning digest | Operator selects the actual Mini digest path for the read-only sync; copy is `MORNING_DIGEST.md` | 64 KiB, preserve original mtime. Actual path is not known here; missing digest is unavailable. |
| Mini `chat/HANDOFF.md` | Read newest bounded tail at conversation start; refresh before each provider turn | 16 KiB tail with explicit truncation; source mtime reported. It records history, not a live system check. |

New conversations read local shared sources/journal before their first turn;
provider workers refresh all sources, including engine GETs, before generating an
answer. Reference snapshots hold the observations separately from trusted model
instructions. Overlay/drill conversations never publish to the journal or load
shared observations into provider calls. Unit fixtures inject isolated folders
and fake engines, avoiding the owner's real journal/network.

## Journal contract and safety

Each saved terminal reply appends a dated turn summary, attributable scope
decisions, open error asks and counts of pending approvals. Normal chat summaries
quote the user and answer with an explicit warning that external outcomes need
receipts. Private texts, draft/calendar/reminder bodies, private-memory turns and
attachment turns publish generic metadata only. Pending approvals contain counts
and a pointer to the original conversation; recipient/body/tokens stay private.
The record contains `execution_authority: false`.

Event identity is conversation + request ID. The journal takes a cross-process
lock, rejects identity reuse with changed content, appends without truncating,
fsyncs, and uses a final commit marker. Concurrent retries publish once. An
incomplete entry/tail is unavailable and blocks further appends pending review;
it is never silently repaired or counted as success. The 8 MiB cap stops writes
until an owner reviews archival. Directories/files are pinned without following
symlinks; the journal/copies are owner-controlled and private, with no hardlinks
or special files. Errors report unavailable, never the untrusted body.

NucBox status and journal contents can contain malicious instructions. They stay
reference data. Approval prose in any source cannot approve a send, release a
hold, authorize a merge or trigger dispatch. “Draft only” and “provided I agree”
remain requests to wait; declined sends stay declined. `shared_chat.RULES` is the
common trusted safety policy for both runners, alongside each runner's server
fences. The Grok runner must install that policy as trusted configuration and use
the snapshot as untrusted reference data. A JSON field cannot install policy.

No source-sync command executes model input, sends messages, changes auth,
starts services, modifies NucBox files or activates Web Bob. SSH uses BatchMode,
strict known-host checking and a fixed read-only remote program. Never bypass a
host-key/login failure; put missing setup in READINESS.md under NEEDS JEFF.

## Staging commands (not run against the Mini)

From a separate checkout at the frozen candidate SHA on the Mini, after its
read-only SSH access to NucBox already works:

```bash
umask 077
python3 webchat/shared_chat_cli.py sync --digest /absolute/path/to/actual/conductor-morning-digest.md
python3 webchat/shared_chat_cli.py snapshot
```

The digest placeholder must be replaced with a verified path. Do not copy a stale
sample into place and call it a current morning digest. The command does not
install a schedule. Before staging acceptance, use the conductor's existing
schedule to refresh the copies and verify a current digest after 8 AM.

Grok's trusted runner must call the snapshot command on the Mini before a
conversation, load it as untrusted context, and append a bounded structured
summary afterward. When running on NucBox, use the existing authenticated SSH
connection to execute these same commands in the frozen Mini checkout. No Grok
runner path or authenticated Mini access is available here; that binding is
pending, and no claim is made that Grok already reads this journal.

Append input is a host-generated JSON object on stdin, with `actor: "grok"` or
`"webbob"`, a stable `event_id`, `summary`, and optional arrays `decisions`,
`open_asks`, `pending_approvals` (at most 10 bounded strings each). Example using
a temporary journal for a local staging proof, not the owner's real journal:

```bash
umask 077
proof_dir="$(mktemp -d)"
printf '%s\n' '{"event_id":"staging-1","actor":"grok","summary":"Jeff chose the blue arrangement.","decisions":["Blue arrangement proposed for review."],"pending_approvals":["Review original card; no send authorized."]}' \
  | python3 webchat/shared_chat_cli.py append --folder "$proof_dir"
python3 webchat/shared_chat_cli.py snapshot --folder "$proof_dir"
```

For acceptance, prove Grok -> Web Bob and Web Bob -> Grok pickup at the final SHA,
with current source timestamps, unavailable-source honesty, no duplicate journal
entries after restart, no private recipient/body leakage, and zero real sends.
Voice snapshot compatibility and actual Grok hook operation still need staging
verification. Passing the offline tests is not this production proof.

Offline tests: `PYTHONPATH=webchat:state python3 -m unittest test_shared_chat -v`.
The tests cover actual Chat/provider prompt integration, both journal actors,
concurrency/restart replay, crash tails, source age, fixed GET/SSH boundaries,
link/permission rejection, credential/tag rejection, privacy and journal outage
without losing the completed reply. No real network/provider/send is used.

## Stack Ops runtime status

Explicit `$stack-ops` / `Stack Ops` selection now reads the configured shared
snapshot alongside the bounded local status helper. It reports each shared
source's availability, observation time and freshness. Journal/source prose does
not become a status command, health verdict or approval. This read-only route
does not install the source sync or Grok hook; the staging gates above still apply.
See [runtime integrations](docs/WEBBOB-RUNTIME-INTEGRATIONS.md).

## Private personal drafts

Saved personal draft turns carry `private_draft` on both user and reply rows.
The provider view also recognizes legacy `drafts` provider rows and the active
personal draft's request before persistence, removes their private state/title,
and excludes those pairs from generic model context. Coordination and typed
reply journals exclude them; HANDOFF keeps the existing generic private-action
summary and pending count. Declines are recorded durably in the original private
conversation. Historical journal/source approval prose cannot reactivate them.
No previously appended journal entries are edited or deleted. Tests include
actual Chat/provider/journal boundaries and authenticated HTTP refusal replay;
live Grok runner and Mini source provisioning remain unproved.

# Web Bob / Grok Bot go-live gaps

Inventory: 2026-10-18. This candidate starts at PR #153 `93bec84` and consolidates
#155 `5144320`, #156 `be13059`, #157 `92e0946`, #158 `065de01`,
#159 `cf80efd`, #160 `151d4ee`, plus #130's memory design. Imports are code
availability, not production integration or exact-head review approval.

Reference: Jeff's `~/.local/share/storypool/parity/GROK_BOT_PARITY_SPEC.md`,
repo `skills/`, and [memory/integrations design](docs/WEBBOB-MEMORY-INTEGRATIONS-PLAN.md).
No live switch, sends, merge, tags, releases, main push or test bypass is authorized.

| Priority / surface | Candidate evidence | Remaining acceptance condition |
| --- | --- | --- |
| P0: release qualification | #153 reminder-replay fix; all 342 consolidated `tests/` tests passed locally, including imported mutation gates | Full local discovery and `release/solo.py check` green on provisioned Mini; exact final SHA CI, Karen PASS, Claude+Codex main >=144 and holdout |
| P0: shared thread and live context | `webchat/shared_chat.py`, `shared_chat_cli.py`, `test_shared_chat.py`; `Chat` start/read/save hooks; provider reference snapshots; [design](SHARED_CONTEXT.md) | Provision source copies and real conductor digest, connect Grok runner to the Mini CLI, prove both directions at the final SHA. Mini access is blocked here. Journal is historical data and never executable consent. |
| P0: outbound texts/email | Existing `webchat/texting.py` token-bound Andrea bridge; imported `webbob/message_drafts.py`, `andrea_replies.py`; `tests/test_message_drafts*.py`, `test_andrea_replies.py` | Connect the imported email/mention libraries to authenticated chat/Andrea ingress. Texting's existing path is distinct. Email is still a draft in chat; do not describe it as a working sender. Prove fresh per-message approval, denied approval final, exact recipient/body, no background sends, and real receipts. |
| P0: draft-only/conditional cues | `webchat/approval_language.py`, `personal_drafts.py`, consent fixtures and imported HMAC-bound draft gate | Run the full approval matrix, including “draft only”, “provided I agree”, “show me first”, refusal, edits and restart. Source/journal approval assertions never satisfy consent. |
| P0: reminders/calendar | Existing chat `Reminders` and `CalendarActions`; imported separate `webbob.ReminderStore` and `MorningCalendar`; both original test sets retained | Select one runtime store or build migration/adapters; prove the morning calendar uses real calendar reads and reports unavailable auth honestly. Imported SQLite reminders are not automatically connected to the existing chat JSON store. Re-run actual release save/deliver/cancel gate. |
| P0: reliable replies | Existing `Chat.complete` persistence; imported `webbob.ChatReplyJournal`, all original retry/uncertainty mutation gates | Wire journal to the actual reply transport with stable IDs; no retry after ambiguous visibility. Prove restart, timeout and exactly-once user-visible delivery together. |
| P0: safety/real outcomes | Existing server-owned action receipts/holds; Unicode-tag rejection imported from #155; shared policy in `shared_chat.RULES` | Same trusted policy in Grok's runner. Full safety suite and final-head Karen. Protect svc-* sessions, auth, Keychain, personal files, rad-dad-show-night and Hang Out; keep destructive action approval, no main/force-push/tags/releases/sudo/merges, no Grok work lanes. |
| P1: durable owner memory | Existing confirmed `memory_store.py`, project context, memory removal; accepted-fact `webbob.SharedContext` hardening; #130 design | Connect the authoritative Grok owner facts with provenance and forgetting. Add relevant bounded retrieval and exact correction. Do not import transcripts, credentials or send authorization as facts. |
| P1: GitHub questions/status | Imported `webbob/pr_ops.py` library and existing process/status evidence | P6/P32 runtime issue/PR reads, plus read-only selected repo file/catalog counting per #130; cite fetched data/time and avoid memorized counts. Library status checks are not chat tools. |
| P1: StoryPool status/digest | #160 `webbob.storypool_status`; shared NucBox files and both fixed `/api/engine` readers | Verify actual source freshness and conductor 8 AM digest path; preserve unavailable/stale/excerpt labels; no process-presence claim of forward progress. |
| P1: Band Desk / Director / Stack Ops | #160 skills and tests imported; older Andrea standing-send exceptions removed | Connect reviewed, explicitly selected skill content to Web Bob's runtime; definitions on disk do not prove automatic skill routing. Band Desk never sends; Director proposes; Stack Ops reads only. |
| P1: read-only tools | Existing bounded local files/terminal/search; imported tool-host/research/Workspace primitives | Integrate selected Gmail/Drive/GitHub reads with dedicated least-privilege auth; no token-file reads. No live auth setup or tool execution claimed. |
| P1: conductor/routines/ops | Existing task dispatch, queue, hold and status paths | Prove 8 AM routine/digest, capacity and quota admission, load/swap/disk guard thresholds, NucBox lane caps/reservations, bounded retry/fix loop, watchdog and usage accounting at the runtime boundary. |
| P1: staged go-live/rollback | Release code already exists; no new activation wrapper in this run | Add and test an explicitly staged health-check/auto-rollback script, pin full predecessor SHA resolving `cf83a9a`, preserve state, document command. Do not execute it without Jeff's explicit go-live OK. |
| P2: broader parity QA | Spec calls for local Karen vs Grok-Karen on the same 10 PRs, >=90% agreement, false PASS = 0 | Produce read-only comparison/scorecard without using Grok as a work lane or inferring PASS from labels. |

## Remaining P-series drafts

No P-series head below is an ancestor of #153. Some base functionality overlaps;
inspect each diff rather than replacing newer runtime files with a whole branch.
This run imported #130's design only. Source PR metadata is captured in the
external readiness evidence (`evidence/20261018-1300/parity-prs.json`).

| Drafts | Gap / treatment |
| --- | --- |
| #106 P2, #107 P4, #108 P7 | Honest lookup results, relevant memory recall, grounded multi-step status. Their dedicated regression modules are absent from the starting candidate. Integrate after checking existing lookup/status behavior. |
| #109 P16 | Opt-in execution lease; state module absent. Review interaction with current dispatch/ownership; never grant implicit machine execution. |
| #113 P10, #114 P8 | Scanned-PDF OCR and page/excerpt provenance. P10 scanner absent; P8 files overlap newer candidate files and need a hunk review. |
| #115 P23, #116 P20 | Evidence-based failure recovery and conversation-scoped action history; dedicated modules/UI absent. |
| #117 P18 | Routine pause/resume overlaps existing reminders; review behavior and preserve current consent rules. |
| #118 P19 | Prerequisite failure report, not a working email-reply feature. Still needs real mail read/draft context and fresh send approval. |
| #119 P27, #120 P24 | Honest image fallback and exact approved memory replacement; dedicated modules absent. |
| #121 P21, #122 P25 | Attachment-to-reviewed reminder and continuation of a fetched public page; dedicated modules absent. |
| #123 P22, #124 P26 | Saved-job checklist and visible read-aloud state/truncation; dedicated UI modules absent. |
| #125 P29, #126 P32 | Drive replacement proposal and bounded selected GitHub item body; dedicated read/proposal modules absent. |
| #130 | Memory/integration plan imported unchanged as design; implementation acceptance still open. |

Implementation order after this run: finish provisioned release/Karen checks;
connect the approved draft/reminder/calendar/reply adapters without dual stores;
complete memory and GitHub reads; finish shared-source/Grok staging proof and
explicit skill routing; stage rollback packaging; score the frozen final SHA.
Jeff's live-switch decision remains the last gate.

# Preserve the serving Web Bob feature set

PR #161 is a reference branch. It must not merge as a single release.
This checklist is a specification, not evidence that a feature passed.
All rows start **NOT RUN**. The serving snapshot remains unchanged.

## Build identity and evidence

The serving snapshot identifies itself as
`cf83a9a80e0426d6998a0bf7b3a0574e52ac8e1a`. It is a file snapshot,
so Git commands in its directory do not establish the running version.
Before qualification, inventory the complete served files and pin their hashes,
startup selector, dependency closure, process ownership and build manifest.
A historical scoped-pass marker does not establish current recovery readiness.

Every result must bind to the candidate's exact complete build, runtime,
scenario, timestamp and independent receipt. Missing modules, NOT RUN,
partial results or an unresolved rollback marker block release. Keep sensitive
inputs and raw evidence in private state; public fixtures must be synthetic.
A module inventory alone does not establish behavioral parity.

## Required feature families

| Family / serving modules | Required behavior on the complete candidate | Result |
| --- | --- | --- |
| Chat: chat_intent, answer_intent, answer_fragments, structured_reply | Ordinary and task chat route correctly; streamed replies complete and survive reload. | NOT RUN |
| Reply authority: reply_contract, reply_guard, reply_authority, claim_scope, claim_evidence, source_evidence, result_provenance | Claims match actual evidence; failed, pending and unverified actions are never reported as completed. | NOT RUN |
| Conversation: conversation_focus, decision_context, draft_revision, catchup_contract | Follow-ups, revisions and catch-up preserve the selected project and conversation. | NOT RUN |
| Memory: memory_store, memory_view, memory_removal | Accept and retrieve authorized memory after restart; delete it and prove it no longer surfaces, including across teammates. | NOT RUN |
| Actions: actions, reminders, texting, quiet_hours | A reminder survives restart without duplication; outbound delivery needs fresh exact individual approval and an honest receipt. | NOT RUN |
| Voice/media: voice, chat_media, pdf_text | Phone voice starts, interrupts and hangs up; supported uploads/PDFs are read with ownership and privacy boundaries. | NOT RUN |
| Jobs: job_queue, jobs_view, job_card_view, task_dispatch, dispatch_receipts | Submit, inspect, cancel/recover and independently verify a real bounded job; no fabricated delivery receipt. | NOT RUN |
| Workers: worker_assignment, worker_activity, worker_evidence, max_mode, lane_collector, resource_inventory, resource_decision | Resource/worker identity is current; limits, leases, stale recovery and exclusions prevent duplicate or unauthorized workers. | NOT RUN |
| Projects/team: project_context, project_handoffs, project_reports, teammates, instinct | Bob, Andrea and Karen share only authorized context; handoffs keep provenance and actual receiver acknowledgment. | NOT RUN |
| Music: music_notebook, music_demo, music_local_sketch | Retrieve/edit an authorized notebook and create an inspectable demo/sketch artifact; keep originals and project scope. | NOT RUN |
| Recovery: failover, live_failover, handback, startup recovery | Fail provider/startup safely, recover without duplicated effects, and hand back with correct state. | NOT RUN |
| Operations: ops_panel, billing, capabilities, build_info, status_observation, tab_status | Display actual runtime identity, costs/usage and freshness; unavailable data stays unknown. | NOT RUN |
| Improvement: self_improvement, bob_gaps, bob_parity_eval, instinct evaluation | Run the parity evaluator against the pinned serving and candidate builds; record regressions and useful outcomes separately from test totals. | NOT RUN |
| UI: static tabs, shell, utility controls and login | Unauthenticated root redirects303 to login; login returns200; authenticated tabs work at375/390px with keyboard/input controls visible. | NOT RUN |

Inventory aliases or relocated modules need a documented behavior mapping;
absence cannot be dismissed as a rename. The existing fourteen capability and
four recovery checks in `config/parity-checklist.json` remain mandatory as well.
This document does not change `webbob.parity_gate` or claim it is wired into
any currently serving release executor.

## Small implementation stack

Each PR covers one concern and stays below approximately300 lines of real code.
Each has affected regression checks, required green CI, a privacy-clean diff
and independent exact-head Karen PASS. Reassess the stack against actual source
rather than copying private history or capture fixtures from #161.

1. Build/runtime identity and pinned complete-file manifests.
2. Authentication and login gate.
3. Private memory storage, migration, restore and deletion.
4. Durable reminders and quiet hours.
5. Exact action approval, stale approval rejection and delivery receipts.
6. Phone layout, keyboard and voice interruption controls.
7. StoryPool controls, resources, projects and authorized shared context.
8. Release tooling, canary identity and automatic rollback.

Additional focused PRs must cover every remaining family above. This ordering
is a review plan, not permission to ship an incomplete replacement. Existing
qualified work may be reused with its exact provenance; do not repeat unchanged
reviews or long local suites merely to increase test counts.

## Release gate

- Clear complete source/history/license privacy before publication or release;
  never publish profiles, contacts, messages, automation exports or secrets.
- Qualify every family on one final complete build, including reviewer scoring,
  shared context and deletion. Preserve the serving build and all rollback data.
- Require green exact-head CI including privacy, complete exact-head Karen PASS,
  and a bounded NucBox or local canary with the intended pinned runtime.
- Demonstrate automatic rollback with the actual documented release tool.
  Never manipulate protected service screens directly.
- Obtain the owner's final go-live acceptance after presenting concrete evidence.
  Standing approval to merge qualified PRs is separate from that release decision.
- Activate only through the documented release tool. Smoke local and tailnet
  root/login, the candidate test script and new traceback counts twice at least
  sixty seconds apart. Automatically roll back any failure and verify recovery.
- Report deployed behavior and independently verified production completions
  separately from passing checks. No result in this checklist is pre-approved.

READY — Web Bob capability parity matrix, 22 rows, evidence-based (2026-09-28, live tip `a777736`).

# Web Bob vs. Bob the Bot — Parity Matrix

Compiled 2026-09-28 ~09:21 CT. Read-only compilation from existing evidence under `conductor/reviews/` and `conductor/STATUS.md` / `conductor/dashboard.json`. No code changed, no deploy, no notify, no Grok/xAI.

Status legend: **LIVE** (in production at the cited SHA/tip) · **READY** (built, tested, LIVE-reviewed, not yet deployed) · **HOLD** (built or in progress, blocked by the fixed deploy order) · **MISSING** (not built on Web Bob; may or may not exist on Bob the Bot) · **UNKNOWN** (no evidence found this pass).

Fixed deploy order (per `LOOP-RUN-0810/0916-SUMMARY.md`): **texting LIVE → gaps → media → voice → UI → Instinct**. Nothing below this line may deploy out of order regardless of its own readiness.

## Live baseline (2026-09-28 ~09:21 CT)
- Prod `/api/version`: `a777736` (full `a777736b3f0a37c82b0c4c62be8c91117c4c9881`, built_at 2026-09-28T09:04:32+00:00) — base chat + coding-lane dispatch + draft-PR flow only.
- Texting: **not LIVE**. Tip `9cfe548` had LIVE Gemini+MiniMax BOTH_PASS (`TEXTING-LIVE-0810.md`) but deploy attempt2 came back `FAIL_OR_ROLLBACK` (`TEXTING-DEPLOY-0810.md`, `WEBBOB-TEXTING-FAIL-0810.md`) — live-replay job `webchat-53ff7beab93c5adaad5c4177ec9b9e7f` claimed a fix without re-running the real tests the gate expects. Rolled back to `a777736`, verified (`rollbacks/webbob-texting-20260928-083126`). A fix+redeploy lane (`lane-webbob-texting-diagdump-fix-0916`, screen pid 10351) is **already running** as of this matrix's compilation — not something this task queues or duplicates.
- `~/STOP-WEBBOB` does not currently exist (checked at compile time); the safety-finding hold noted in `WEBBOB-PARITY-0927.md` is not currently blocking.

## Matrix

| # | Capability | Bob the Bot | Web Bob status | Tip SHA / evidence | Blocker |
|---|---|---|---|---|---|
| 1 | Memory/recall — **read** | LIVE, reads `bob-brain/memory/profile.md` | **LIVE** | `WEBBOB-PARITY-0927.md` row 6; `webchat/providers.py:324-325` reads up to 28,000 chars into every fallback prompt | None |
| 2 | Memory/recall — **write** ("remember that…") | LIVE, agent appends dated lines to `profile.md` | **HOLD** | `draft/webbob-gaps-1725` tip `70d59e3`; `bob_gaps.append_profile_memory`, race fixed in `GAPS-FIXED-2143.md` (fcntl lock + atomic write); `GAPS-PROGRESS-1841.md` (269 tests OK) | Bundled in "gaps" — waits for texting LIVE first |
| 3 | Routines / always-on services | LIVE — 4 launchd services (job-runner, reviewer, dashboard-updater, watchdog) | Partial/LIVE (ops only, not user routines) | `STATUS.md`: "SERVICES: 4/4 healthy"; self-improve job chat-surfaced `app.py:702-914` | No user-facing "set a routine" chat command exists on either side |
| 4 | Multi-LLM workers (Codex/Claude/Cursor/Gemini/MiniMax, never Grok) | LIVE, 5-lane dispatcher | **LIVE** | `dashboard.json` lanes: claude/codex/cursor/gemini/mini/minimax all `state: ready`; `webchat/providers.py` 5-provider failover; Grok present only in regex as a policy-excluded non-lane (`job_queue.py:43,123`) | See row 11 for known reliability gaps in this lane (not a Grok issue) |
| 5 | Multi-LLM reliability (failover completeness, concurrency, usage-cap tiering) | N/A (desktop Bob doesn't share this dispatcher code) | **MISSING** (gaps, not yet a build item) | `WEBBOB-MAX-GAPS-0927.md` #2–#6: explicit-Claude chat has no failover tail; Gemini/MiniMax capped to 1 concurrent job despite being stateless APIs; no 70/85/95% usage-cap tiering and Gemini is fully uncapped; auto-routed analysis tasks always try Claude last regardless of fit; no queueable "mini CPU" worker | Queued below — draft-only, independent of the texting→…→Instinct chain |
| 6 | "Go to the max" — one goal fans out across every idle lane | Partial — job rows already carry `group_id`/`group_size`/`group_index` (e.g. `group_id max-d3fb9012…`, size 4, fanning WebJam/AdoptIQ/StoryBoard/Fantasy) per `logs/lane-webbob-texting-diagdump-fix-0916.log` queued-job dump | **MISSING** for chat-triggered fan-out | `WEBBOB-MAX-GAPS-0927.md` #1: `task_dispatch.submit_task` is strictly 1 request → 1 queue row → 1 worker; no phrase recognition for "go to the max" in `parse_work`; `council.py` fan-out only fires on explicit `run council:` and never executes code | Queued below |
| 7 | Dispatch/status — coding lanes generally | LIVE | **LIVE** | `job_queue.py` + `task_dispatch.py`; jobs land in `next-prompts/INDEX.md`; once-only confirmation receipts (`actions.py:10-35`) | None |
| 8 | Dispatch/status — WebJam PRs | LIVE | **LIVE** (same dispatcher) | PR #160 (draft, CI red on `test_jamulus_native_startup.py`, per `notes-codex` in `STATUS.md`); PR #161 (draft, awaiting Jeff's "feel check" per `HANDBACK-SUMMARY.md`); Cursor queue-22 port-conflict fix landed `3eb3925` | None — this is a live capability; PR #161 itself is waiting on Jeff, not on Web Bob |
| 9 | Dispatch/status — AdoptIQ PRs | LIVE | **LIVE** (same dispatcher) | `HANDBACK-SUMMARY.md`: "Queue after WebJam: … AdoptIQ #26 rebase" | None |
| 10 | Dispatch/status — StoryBoard PRs | LIVE | **LIVE** (same dispatcher) | `HANDBACK-SUMMARY.md`: "StoryBoard #47" queued next; related `story-corner-shelf` PR #10 green CI per `notes-claude` in `STATUS.md` | None |
| 11 | Dispatch/status — Fantasy PRs | LIVE | **LIVE** (same dispatcher), evidence thin | Referenced as one of 4 max-mode projects in the queued-job dump (`group_goal`: "WebJam, AdoptIQ, Stkryboard, Fantasy Football"); no open PR number found in this evidence pass | UNKNOWN current PR # — evidence gap, not a capability gap |
| 12 | Dispatch/status — bob-brain (Web Bob's own build) PRs | LIVE (this **is** how Web Bob itself gets built) | N/A — self-referential | Draft PRs #10, #11 (parity), #18/#20 (texting), #19 (Instinct), all on `rupret007/bob-brain`, draft-only | None |
| 13 | Texting via Andrea (draft-then-yes) | LIVE — Andrea's own `requiresApproval` trust ladder, exact-phrase gate (`send it`/`send it now`/`send now`), AppleScript-only send; desktop Bob never calls Andrea's send API directly | **HOLD/FAIL** — currently rolled back | Tip `9cfe548`; `TEXTING-DEPLOY-0810.md` RESULT: `FAIL_OR_ROLLBACK`; `WEBBOB-TEXTING-FAIL-0810.md`; draft PR #20; fix+redeploy lane `lane-webbob-texting-diagdump-fix-0916` running now | First in deploy order — live-replay honesty gate caught an incomplete-verification answer; must pass before gaps/media/voice/UI/Instinct can deploy |
| 14 | Instinct read/digest/draft (no auto-send) | N/A — Instinct is a Web-Bob-native parity target, not a pre-existing desktop-Bob feature (per `lane-webbob-instinct-0810.md`); desktop Bob reaches the same Instinct thread via `bob-brain/skills/instinct-with-bob-and-andrea` | **READY**, DEPLOY HOLD | Tip `c51860c`; `INSTINCT-READY-0810.md` (411 webchat + 131 services tests, 22/22 Instinct evals); `INSTINCT-LIVE-0810.md` Gemini+MiniMax BOTH_PASS; draft PR #19 | Last in deploy order — waits for texting→gaps→media→voice→UI |
| 15 | Personal todos/reminders (calendar-like) | **MISSING** — no calendar/reminder-app integration found for desktop Bob either | **MISSING** | `WEBBOB-PARITY-0927.md` rows 5 and 11 confirm the gap on both sides; only adjacent feature is an unrelated "song projects" save/list API (`providers.py:36-38`) | Genuine gap on both sides, not a deploy-order HOLD — queued below |
| 16 | File/image attachments | N/A (desktop Bob operates on local files directly, no chat-upload surface) | **READY**, HOLD | Tip `b8aa84a`; `MEDIA-FIXED-2205.md` — 4 critical fixes (bounded upload read, binary secret-scan bypass, `PROCESS_SLOTS` leak, orphan blob on metadata failure); 292+39 tests passed | Second in deploy order after gaps |
| 17 | Voice — live two-way + memos | N/A (no desktop Bob voice feature found) | **HOLD/FAIL** — not yet even HOLD-ready | `WEBBOB-VOICE-MINIMAX-0927.md` VERDICT: FAIL — 3 bugs (IndexError on single-message voice turns, message-timeout regression, KeyError on missing `voice_order`) + 3 security findings (no CSRF check on voice endpoints, no rate limit on token creation, error message leaks architecture) | Must clear its own bug/security bar before it can even queue behind media in deploy order |
| 18 | UI (the deploy-order item distinct from voice) | N/A | **UNKNOWN** | No dedicated branch, tip SHA, or review file found under this name anywhere in `conductor/reviews/` or `conductor/prompts/`; only ever appears bundled as "Voice / UI: behind" in `LOOP-RUN-0810/0916-SUMMARY.md` | Scope is undefined — queued below as an investigate-first lane, not a build lane |
| 19 | Web research | LIVE only informally — relies on the acting CLI agent's own native web tools, not a dedicated script (`bob-brain/skills/ai-r-d-reuse-hunt/SKILL.md` is guidance only) | **READY**, HOLD | Tip `70d59e3` (bundled in "gaps"); `bob_gaps.web_search()` / `format_web_search_reply()`, `User-Agent: WebBob/1.0`; `GAPS-PROGRESS-1841.md` | Bundled in "gaps" — waits for texting LIVE |
| 20 | Screenshots (user-facing chat command) | Partial — proof-of-work tooling only (`bob-brain/skills/mini-paste-working-proof/SKILL.md`), not something Jeff asks for interactively | Partial/HOLD | Command-injection fix + macOS gate for `capture_screenshot()`, bundled in "gaps" tip `70d59e3` (`GAPS-PROGRESS-1841.md`); still QA/dev tooling, not exposed as a Jeff-facing command per `WEBBOB-PARITY-0927.md` row 9 | Same gaps bundle; exposing it as a real chat command is still unbuilt — queued as a stretch item alongside personal reminders if Jeff wants it |
| 21 | Honest status / no empty promises | LIVE, structurally enforced — `BOB-HANDOFF.md` draft-only rules plus the live-replay gate itself | Partial/LIVE at the **conductor gate** level, not inside webchat code | This exact rule is what's currently blocking texting: `WEBBOB-TEXTING-FAIL-0810.md` — a worker "claimed bounded fix... verification incomplete"; the earlier raw-diagnostic-dump regression is already fixed and green (`prior_failure_regression.pass_check: true`, `LOOP-RUN-0916-SUMMARY.md`) | The gate is working (it caught and rolled back a bad claim); the underlying texting-worker honesty bug it caught is not fixed yet |
| 22 | Notify rules (stay quiet unless 100% ready) | LIVE — `ready_to_notify` gate, currently `false` | N/A as a webchat feature | `LOOP-RUN-0810-SUMMARY.md` / `LOOP-RUN-0916-SUMMARY.md`: "Stay quiet unless 100% ready for testing" | This governs when Bob tells Jeff about Web Bob's *own* progress — it's a conductor/ops rule, not something implemented inside webchat itself |
| 23 | Teammates — Andrea | See row 13 (texting) | See row 13 | — | — |
| 24 | Teammates — Karen | Partial — human WebJam QA reviewer; Bob's work must pass her independent review gate, no bot-to-Karen integration | **MISSING** | `wt-webjam-polish/PRE_KAREN_QA.md`: "Physical Art/Music acceptance and independent Karen review" | No reference to Karen anywhere in `conductor/webchat` — nothing to build unless Jeff wants a status surface for her review state |
| 25 | Teammates — Band Desk | **UNKNOWN** | **UNKNOWN** | No occurrence of "Band Desk" found anywhere in the repo under this name (checked `BOB-HANDOFF.md`, all `*.md`, `conductor/`) | Ask Jeff what "Band Desk" refers to before building anything — do not guess |

## Summary counts
- LIVE: 8 (rows 1, 4, 7, 8, 9, 10, 12, 21-conductor-level)
- READY (built + LIVE-reviewed, deploy HOLD): 3 (rows 2/19 gaps bundle, 14 Instinct, 16 media)
- HOLD/FAIL (built or in progress, currently blocked or failing its own gate): 2 (rows 13 texting, 17 voice)
- MISSING (not built, no deploy-order excuse): 4 (rows 5/6 reliability+max-mode, 15 personal reminders, 24 Karen status)
- UNKNOWN (evidence gap): 3 (rows 11 Fantasy PR#, 18 UI scope, 25 Band Desk)

## Queued feature lanes (draft-only; not launched by this task)

Each MISSING / HOLD-behind-texting item below has its own gated lane prompt under `conductor/prompts/`. None of these are started — they are drafts a future tick can pick up once the deploy order allows, or immediately for the order-independent ones (reliability gaps, max-mode, personal reminders, who's-running view, teammate status, UI scope investigation).

| Lane | Covers row(s) | Gate |
|---|---|---|
| `lane-webbob-gaps-deploy-queued-0916.md` | 2, 19, 20 | Deploy after texting LIVE |
| `lane-webbob-media-deploy-queued-0916.md` | 16 | Deploy after gaps |
| `lane-webbob-voice-fix-queued-0916.md` | 17 | Fix bugs/security first, then deploy after media |
| `lane-webbob-ui-investigate-queued-0916.md` | 18 | Investigate scope only; deploy after voice |
| `lane-webbob-instinct-deploy-queued-0916.md` | 14 | Deploy last, after UI |
| `lane-webbob-personal-reminders-queued-0916.md` | 15 | Independent of texting chain; draft-only until Jeff prioritizes |
| `lane-webbob-whorunning-view-queued-0916.md` | 20 (adjacent) | Independent, read-only, no deploy-order dependency |
| `lane-webbob-teammates-status-queued-0916.md` | 24, 25 | Independent; must ask Jeff about "Band Desk" before building anything for it |
| `lane-webbob-maxmode-reliability-queued-0916.md` | 5, 6 | Independent of texting chain (dispatcher-level, not webchat feature deploy) |

No code was changed, no lane was launched, no deploy occurred, no Jeff notification or text was sent, and Grok/xAI was not used, while producing this matrix.

---
name: Priority-aware lane refill
description: >-
  use this when Bob needs priority-aware Cloud/BYOK lane refill policy during
  keep-pressing — WebJam-first; may delegate execution to Lane Dispatcher peer
---
use this when Bob (or any conductor) needs priority-aware Cloud/BYOK lane refill policy during keep-pressing — priority-kernel first, never vanity idle-fill. Bob may **delegate execution** to Lane Dispatcher (SILENT_CAPPED_PEER); this skill remains policy / one-shot fallback on Bob’s open turn.

# Priority-aware lane refill

## Priority kernel (always)
1. Rank-1 product (currently WebJam #155 test path) gets sole coding capacity until Jeff-testable or Jeff-gated.
2. `cloud_fills_mode` is one of: `webjam_focus` | `go_max` | `codex_only` | `frozen`. **Bob is sole writer.** Never freeze and unfreeze different keys in the same turn.
3. GO MAX / GO_MAX_SECONDARY is a **Bob-gated burst** after rank-1 is green or waiting only on Jeff — not a standing identity. Still one WebJam coding lane.

## Who runs the loop (Rank 1)
- **Standing loop:** Lane Dispatcher silent peer (board + Bob-only; never DM Jeff).
- **This skill on Bob:** policy + true in-thread one-shots — do **not** pile multi-minute refill onto Jeff chat turns.
- Do **not** re-enable noisy no-idle every 20m on Bob — Lane owns refill pulse.


## Anti-waste routing (Jeff 2026-09-25) — HARD
Preference order before any refill launch:
1. **BYOK direct** — MiniMax tip critiques; Gemini (`GEMINI_API_KEY`) research/critique/large-context — **not** Cursor Cloud `gemini-*`.
2. **Mac Mini goal paste** (`mini`) — Codex / Claude apps (Jeff’s OpenAI/Anthropic plans).
3. **LOCAL Cursor on Mini** (`local_cursor`) — Composer / local agent; separate spend bucket from Cloud BA; max when Composer headroom.
4. **Cursor Cloud** (`cloud`) — last resort only with spend headroom (Other Models not empty; on-demand Fixed not exhausted; API ≥$2 remaining).

**`BLOCKED_SPEND_WALL` behavior:** if board `cloud_launch.status=BLOCKED_SPEND_WALL` or `cloud_fills_mode=BLOCKED_SPEND_WALL` (or Other Models 100% / on-demand over Fixed / <$2 remaining): **zero new Cloud launches**. Refill via Mini paste + BYOK + Actions CI only. Do not retry-spam Cloud. Path tags on board: `mini` | `byok` | `local_cursor` | `cloud`.

## Model pins (BYOK / Mini first; Cloud ids = last-resort only)
- Codex: **Mini ChatGPT goal paste preferred**; Cloud id `gpt-5.3-codex` only with headroom
- Claude: **Mini Claude.app goal paste preferred**; Cloud id `claude-sonnet-4-6` (or newer sonnet Jeff named) only with headroom
- Gemini: **direct API** (`GEMINI_API_KEY`) first — heavy=`gemini-3.1-pro-preview`, light=`gemini-3.8-flash` (thinkingLevel=low, maxOut≥256), fallbacks `gemini-2.5-flash`/`gemini-2.5-pro`. Never bare `gemini-3.1-pro`. Do **not** pin Cursor Cloud `gemini-*` as default refill. Cloud Gemini = last resort only.
- Grok: conductor on Bob; Cloud `grok-4.6` only with headroom
- MiniMax critiques: BYOK `MiniMax-M2.7` (default) / `M2.7-highspeed` (cheap/fast) / `MiniMax-M3` (hard judgment) via MiniMax Runner peer or [MiniMax BYOK work lane](sand-workflow:minimax-byok-work-lane) — never Cloud; `Text-01` obsolete; music-3.0 410 gated; empty balance 402 until Jeff recharges; Codex = WebJam coding sole

## Refill steps
1. Read spend wall / `cloud_launch` / `cloud_fills_mode`. If `BLOCKED_SPEND_WALL` → skip all Cloud launches; go Mini/BYOK/Actions only.
2. Prefer Mini paste + BYOK before listing Cloud agents. List Cloud agents only when headroom exists; note finished/errored.
3. If rank-1 CI red → **one** coding sole: Mini Codex/Claude paste first; Cloud only with headroom.
4. If rank-1 CI in progress / waiting Jeff → do **not** spray; optional one BYOK critique on that tip (MiniMax capped; once per SHA).
5. Else (burst go_max allowed by Bob **and** headroom): refill FREE leases with explicit model pins + path tag; one lease per repo; skip Show Night unless Jeff reopens. Under spend wall, burst = BYOK/Mini only.
6. Update `llm-work-now.json` with model id, repo, PR, goal, agent id, **path** (`mini`|`byok`|`local_cursor`|`cloud`) for every lane.
7. Quiet to Jeff unless blocker or real advance (Bob front door only).

## Rank 1 hardenings (2026-09-25 ~1:01 AM CT retro)
- Board `lane_dispatcher.status` must be exact **`SILENT_CAPPED_PEER`** (not LIVE).
- Never write `cloud_fills_mode` — Bob only. If Bob set `go_max`, refill secondaries quietly; still **one WebJam coding lane**.
- Messages to Bob: default **`priority:false`** FYI; reserve `priority:true` for CI-red sole / blocker / Karen / mode conflict (Jeff sees Bob chat).
- On tip SHA move for rank-1 PR: note PR-body tip refresh leftover for Bob/Cloud same pulse (do not merge yourself).

## Do not
- Spray Cloud / Gemini Cloud under spend wall or when BYOK/Mini can do the job
- DM Jeff from Lane / MiniMax / Band peers
- Leave duplicate agents on the same repo
- Launch a second WebJam coding agent
- Merge / undraft / Final Build / spend without Jeff

## Durable next-prompts queue (HARD — 2026-09-26 ~20:00 CT ops)
Before inventing refill work on Mini:
1. Prefer `~/Documents/bob-overnight-inject/bin/ops-queue-refill.sh` (reaps stale INDEX RUNNING when screen gone + EXIT/RESULT; copies `/private/tmp/<job>/RESULT.txt` into the job dir; then `pick-next.py --json` + launches). `--dry-run` / `--reap-only` supported.
2. Or at minimum run `next-prompts/pick-next.sh` / `pick-next.py --json`.
3. Exit 0 → launch that READY prompt (mark INDEX row RUNNING). Exit 2 (`NONE`) → **fail closed**: do **not** invent StoryBoard/AdoptIQ/shelf work. Harvest research into `next-prompts/` or wait on CI.
4. While WebJam coding lease is busy / CI wait → pick-next prefers WebJam **non-coding** READY rows only.
5. MiniMax tip reviews: only `/workspace/bin/minimax_verdict.py` (box) or Mini `~/Documents/bob-overnight-inject/bin/review-tip-minimax.sh` — never hand-rolled curl. Wrapper **fail-closed** on empty body or missing `VERDICT` (exit 6/3). Never accept 0-byte `reviews-out/*-minimax.md`.
SoT: `/home/box/conductor/next-prompts-queue-20260926.md`


## Job-watch tick + tip Gemini (HARD — architecture 2026-09-26 ~8:12 PM CT)
1. Local Cursor job watch on Mini **must** run `~/Documents/bob-overnight-inject/bin/job-watch-tick.sh` (stamps `local-cursor-job-watch-state.json.last_queue_tick` and calls `ops-queue-refill.py`). Do not invent work when pick-next exits 2.
2. `ops-queue-refill` now kills **zombie** screens (RESULT/BLOCKER present but screen still listed; EXIT= alone ≠ done) and orphan finished injector screens before refill.
3. Gemini tip reviews: only `/workspace/bin/gemini_tip_assess.py` or Mini `bin/review-tip-gemini.sh` — never hand-rolled curl / low maxOut. Fail-closed on empty or missing `ASSESS_OK`/`ASSESS_BLOCKED`.


## Auto-harvest + closeout honesty (HARD — architecture 2026-09-26 ~8:52 PM CT)
1. On REAP_DONE with **RESULT.txt**, `bin/auto_harvest.py` copies deliverables to `next-prompts/_inbox/` and promotes `queue-ready/*.md` (+ optional `PROMOTE.json`) into new INDEX **READY** rows. Never invent prompts.
2. **EXIT= in a log is NOT success.** Claude session-limit still prints `EXIT=0` with no RESULT — refill marks **BLOCKED** + writes `BLOCKER.txt`, never DONE. Only non-empty RESULT.txt → DONE (+ harvest); BLOCKER-only → BLOCKED.
3. Non-coding job closeout contract asks workers to write `queue-ready/NN-slug.md` so the next tick refills without a human harvest pass.
4. Local Cursor job-watch routine prompt should hard-call `job-watch-tick.sh` (automation runs cannot rewrite other routines — update in chat if still inventing inline).

## Ops 2026-09-26 ~9:15 PM CT
- Coding RESULT with uncommitted/not-committed language → BLOCKED (uncommitted_pass), never DONE.
- New WebJam coding launches require sole worktree on codex/start-ux-copy-polish (see webjam_coding_lease_blocked / webjam_worktree_busy_unpushed).
- Host-checklist MUST_FIX: tip 885a324 draft PR https://github.com/rupret007/webjam/pull/159.

## WebJam coding lease honesty (HARD — architecture 2026-09-26 ~9:21 PM CT)
1. **One coding worktree only:** `~/Documents/webjam-pr158-fold` on home branch `codex/start-ux-copy-polish`. Never invent `~/Documents/webjam-rehearsal-*` (or other `Documents/webjam-*`) to bypass a busy/follow-on lease.
2. After a follow-on tip is **pushed** and no job uses pr158-fold as cwd, `ops-queue-refill.webjam_auto_home_lease_wt()` checks the sole WT back to home. Do not leave it parked on `codex/host-startup-checklist` / `codex/rehearsal-recap-card` forever.
3. Coding-busy detection: INDEX WebJam coding RUNNING **or** live screen with BRIEF `coding lane` / kind=coding / name matching rehearsal|recap|host|checklist|identity|chip|… — **not** unique|novice|ci-handoff research/CI screens.
4. INDEX notes must name the **job dir** (`codex-webjam-…`); parse prefers engine-prefixed dirs over worktree names.
5. Rehearsal tip already drafted: https://github.com/rupret007/webjam/pull/160 (`6b8d069`) — dual-review when CI settles; do not re-implement on a second WT.

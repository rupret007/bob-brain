---
name: Priority lane refill
description: >-
  use this when Bob needs to refill coding/critique lanes — prefer BYOK and Mac
  Mini over Cursor Cloud; WebJam-first; never vanity Cloud spray
---
# Priority lane refill (Bob conductor)

Replaces always-on Lane Dispatcher peers.

## Anti-waste routing (Jeff 2026-09-25)
Prefer paths that do **not** tax Cursor Ultra Other Models:
1. **BYOK direct** (`byok`) — MiniMax (`MINIMAX_API_KEY`); Gemini (`GEMINI_API_KEY`) for research/critique/secondary work that does not need a Cursor VM.
2. **Mac Mini goal paste** (`mini`) — Codex (ChatGPT) and Claude apps — Jeff’s OpenAI/Anthropic plans.
3. **LOCAL Cursor on Mini** (`local_cursor`) — Composer / local agent in desktop Cursor app (Cursor Models/Composer pool). Drive via computer control. Separate from Cloud Background Agents — max when Composer headroom exists.
4. **Cursor Cloud Background Agents** (`cloud`) — **budget-gated last resort only**. Need Cursor-hosted checkout **and** spend headroom (Other Models not empty; on-demand Fixed cap not exhausted; API ≥$2 remaining). Banned under BLOCKED_SPEND_WALL.

**Ban:** do not launch Cursor Cloud `gemini-*` soles when the Gemini API key can do the job. Do not spray Claude/Gemini/Grok Cloud for idle keep-pressing. Tip critique → MiniMax BYOK only.

## Priority kernel
1. Rank 1: WebJam sole coding lane + CI watch + Karen MATCH + Jeff Final Build when Jeff wants to test.
2. Rank 2: secondary FREE leases only if Rank 1 is green, waiting on Jeff, or blocked on hosted CI with no coding work left.
3. Modes: `webjam_focus` | `go_max` | `codex_only` | `frozen` — one mode only; no freeze/unfreeze flip-flops in the same hour. `go_max` still respects anti-waste routing and the spend wall.

## Model pins (explicit)
- Codex Mini: ChatGPT Codex goal paste (preferred when Mini free)
- Claude Mini: Claude app goal paste (preferred when Mini free)
- Local Cursor Mini: Composer/local agent (`local_cursor`) — max Composer pool; not Cloud BA
- Gemini: **direct API** (`GEMINI_API_KEY`) — not Cursor Cloud `gemini-*` by default
- MiniMax: BYOK `MiniMax-M2.7` / `M2.7-highspeed` / `MiniMax-M3` via minimax-byok skill — never Cloud
- Cursor Cloud (last resort, budgeted): Codex `gpt-5.3-codex`, Claude `claude-sonnet-4-6`, Grok `grok-4.6` — only with headroom

## Always
1. One lease per repo; one WebJam coding lane max.
2. Show Night PARKED unless Jeff reopens.
3. Cancel duplicates on same repo/goal; never cancel a running Codex workhorse unless Jeff says stop.
4. Update `llm-work-now.json` with repo/PR/goal/status/**model**/**path** (mini|byok|local_cursor|cloud) for every lane.
5. Quiet to Jeff unless gate or real advance.
6. If Cloud launch returns usage / ≥$2 remaining / on-demand wall → stop Cloud fills; fall back to Mini + BYOK; do not retry-spam.

## Do not
- Spray Cloud to keep models busy
- Route Gemini through Cursor when BYOK exists
- Launch second WebJam agent
- Merge / undraft / Latest / send without Jeff
- Wake parked specialist bots for refill

## When a Cloud agent finishes
Refill only under the priority kernel + anti-waste routing. If Rank 1 needs attention, do that first. If spend wall is up, refill via Mini/BYOK only.

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


## Uncommitted PASS + WebJam worktree lease (HARD — ops 2026-09-26 ~9:15 PM CT)
1. Coding RESULT that admits uncommitted / not-committed changes, or a dirty tracked worktree named in RESULT/BRIEF, is **BLOCKED** (`BLOCKER: uncommitted_pass`) — never DONE. Coding closeout must commit+push the draft tip before RESULT PASS.
2. Sole WebJam worktree `~/Documents/webjam-pr158-fold` must be on `codex/start-ux-copy-polish` (and not ahead of origin) before launching a **new** WebJam coding job. Follow-on branches (`codex/host-startup-checklist`, etc.) occupy the lease until the draft PR exists and the worktree is returned to the #158 polish branch. Gate: `webjam_coding_lease_blocked()` in `ops-queue-refill.py` → `FAIL_CLOSED: webjam_worktree_busy_unpushed`.
3. Host-checklist MUST_FIX tip `885a324` → draft PR https://github.com/rupret007/webjam/pull/159 (base #158). Dual MiniMax PASS + Gemini ASSESS_OK in `reviews/webjam-885a324.md`.

## WebJam coding lease honesty (HARD — architecture 2026-09-26 ~9:21 PM CT)
1. **One coding worktree only:** `~/Documents/webjam-pr158-fold` on home branch `codex/start-ux-copy-polish`. Never invent `~/Documents/webjam-rehearsal-*` (or other `Documents/webjam-*`) to bypass a busy/follow-on lease.
2. After a follow-on tip is **pushed** and no job uses pr158-fold as cwd, `ops-queue-refill.webjam_auto_home_lease_wt()` checks the sole WT back to home. Do not leave it parked on `codex/host-startup-checklist` / `codex/rehearsal-recap-card` forever.
3. Coding-busy detection: INDEX WebJam coding RUNNING **or** live screen with BRIEF `coding lane` / kind=coding / name matching rehearsal|recap|host|checklist|identity|chip|… — **not** unique|novice|ci-handoff research/CI screens.
4. INDEX notes must name the **job dir** (`codex-webjam-…`); parse prefers engine-prefixed dirs over worktree names.
5. Rehearsal tip already drafted: https://github.com/rupret007/webjam/pull/160 (`6b8d069`) — dual-review when CI settles; do not re-implement on a second WT.

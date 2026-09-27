---
name: Local Cursor Mini agent
description: >-
  use this when driving local Cursor app on Jeff’s Mac Mini (Composer / Cursor
  Grok) via shell instead of Cursor Cloud Background Agents
---
# Local Cursor Mini agent

## When
Use when driving the **local Cursor app** on Jeff’s Mac Mini for coding — especially to use the **Cursor Models** bucket (Composer / Cursor Grok) instead of Grok-Bot → Cursor Cloud Background Agents (Other Models).

## Machine
Only `Jeffs-Mac-mini.local` (`machineId` `53abfd07-b321-433b-b068-55620c6c756d`). Use Mini Shell / osascript / screencapture — not box computerUse.

## Launch
1. `open -a Cursor` (optional UI).
2. Prefer CLI:
```bash
CUR=/Applications/Cursor.app/Contents/Resources/app/bin/cursor
cd /absolute/checkout
"$CUR" agent --model composer-2.5 -f --trust -p "…"   # Cursor Models
# or: --model cursor-grok-4.6-high
```
3. Prefer `composer-2.5` / `cursor-grok-*` when sparing Other Models. Avoid starting `gpt-5.3-codex` / Claude / Gemini via this CLI if the point is anti-double-dip (those often tax Other Models).
4. Screenshot + log under `~/Documents/bob-overnight-inject/local-cursor-…/`.
5. One lease per checkout; never second WebJam sole; Show Night PARKED — leave Allow-delete alone.
6. No merge/undraft/Final Build/Latest without Jeff.

## Full notes
See `/home/box/conductor/local-cursor-mini-playbook.md`.

## Fail-closed (2026-09-25 ~2:00 AM CT)
- Absolute bin only: `/Applications/Cursor.app/Contents/Resources/app/bin/cursor` (PATH `cursor` often missing on Mini).
- Every launch: `--model composer-2.5 -f --trust -p` (or `--print`).
- Empty stdout/log = **FAIL** → one retry with `--workspace /Users/jeffstory/Documents/bob-overnight-inject` (or the checkout). Second empty = **STALL**.
- Playbook: `/home/box/conductor/local-cursor-mini-playbook.md`

## Active lane (Jeff 2026-09-26 ~11:56 AM CT)
- `local_cursor` is a **first-class** coding lane alongside Mini Codex/Claude — not an optional spare.
- When Codex UI shows **Error in message stream** after one Retry, take (or keep) the **one** WebJam coding lease here; park duplicate Codex STEER; leave DRAFT; no Cloud BA; no Grok worker.
- Proven fold: WebJam #157→#158 tip `0e154e8` ~12:00 CT while Codex stream was dead.

## Job watch tick (HARD — architecture 2026-09-26 ~8:12 PM CT)
Routine **Local Cursor job watch (Mini)** must invoke:
`~/Documents/bob-overnight-inject/bin/job-watch-tick.sh`
That reaps zombie/orphan screens, runs `ops-queue-refill.py`, and stamps `last_queue_tick` on `local-cursor-job-watch-state.json`. Never invent refill work outside the queue.

On REAP_DONE, tick → refill also runs `bin/auto_harvest.py` (inbox + `queue-ready`→READY). EXIT= without RESULT → BLOCKED/BLOCKER, never DONE (Claude session-limit trap).

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

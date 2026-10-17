---
name: Bob Codex queue inject
description: >-
  use this when Bob needs to steer, resume, Set Goal, Cmd+N new chat, or
  follow-up a Jeff-watched ChatGPT Codex / Astra thread on the Mac Mini without
  Jeff pasting — includes Goal progress-row controls and resource-discipline
---
# Bob Codex queue inject

## When
Jeff is watching a named ChatGPT.app / Codex Goal on the Mac Mini and Bob must inject a follow-up, resume, Set Goal, or steer without paste — and must use Astra/Codex resources correctly (Jeff 2026-09-22: know the controls; use them well; keep getting better).

Pair with [Codex Goal mastery](sand-workflow:codex-goal-mastery) (what to write) and [Codex prompt audit](sand-workflow:codex-prompt-audit) (prove it landed).

## Machine
Only `Jeffs-Mac-mini.local` (`machineId` `53abfd07-b321-433b-b068-55620c6c756d`) until Jeff reopens other Macs. For Mini GUI, use Mini Shell/screencapture/osascript — not box computerUse.

## New chat (Jeff 2026-09-22)
- **⌘N (Cmd+N)** opens a new ChatGPT Codex chat on the Mini.
- Use a **fresh chat** when switching projects (e.g. Manic audit vs WebJam) so an active Goal is not yanked mid-flight.
- After Cmd+N, confirm idle composer (`Do anything`), then paste `/goal …` and Return/send.

## Resource discipline (hard)
1. **One coding lane** on a checkout: Astra/Codex OR Cloud — never dual-lease the same WebJam tree.
2. **Astra does the heavy coding**; Bob does light OCR/unstick/audit.
3. **Prove Working / Pursuing goal** before claiming inject done. Paste alone is never done.
4. **After "Goal achieved"** → write a **new** ambitious clean Goal (six-part). Do not thrash resume.
5. Prefer fewer, sharper Goals over rapid CONTINUE spam. If vague mid-run: tighten Goal, don’t spam.
6. **Closeout files:** every inject that creates `~/Documents/bob-overnight-inject/<job>/BRIEF.md` must end with `RESULT.txt` or `BLOCKER.txt` in that same folder before Bob calls the job done. BRIEF-only is an orphan (Logic MCP 3.17, 2026-09-25 13:10 CT).

## Goal progress-row controls (desktop)
Docs: https://learn.chatgpt.com/docs/long-running-work — progress row pause / resume / edit / clear.

| UI state | Correct action |
| --- | --- |
| **Goal stalled / paused** | Click the **branching-arrow** (fork) next to the status chip — Jeff’s unpause control. |
| **Goal achieved** | Clear composer; **Set Goal** / `/goal` fresh six-part contract; blue-send. |
| **Working / Thinking** | Healthy — quiet unless steering. |
| **Error in message stream** | Click **Retry once**. If still Error after ~90s (no Working/Pursuing): write `BLOCKER.txt`, stop Retry/STEER spam, failover coding sole to `local_cursor` or Claude (same lease). Jeff may click Retry later. (2026-09-26 ~11:54–12:02 CT) |
| Queued follow-up while turn live | Paste **Do anything**, then **→ Steer** on the queued-message row (not progress-row play/pause, not Stop). |
| Fresh idle composer | Paste INTENDED starting with `/goal`; Return/send. |

### Anti-patterns
- `/goal resume` glued to CONTINUE → **Replace current goal?** (Cancel).
- Opening stalled chip before Steer.
- Claiming sent while composer still shows text.
- Shell without `machineId`.
- Dual-lease Cloud + Codex.
- Hijacking an in-flight Goal thread for a different project instead of Cmd+N.
- Claiming done when the inject workdir has BRIEF but no RESULT/BLOCKER.
- STEER or second Retry while UI still shows **Error in message stream** (stream dead ≠ Working).

## Paste target
**Do anything** / Goal composer **ABOVE** terminal. Never the shell. Composer text for a new Goal must start with `/goal`.

## Recipe
1. Screenshot; confirm thread.
2. If switching projects → **Cmd+N** new chat first.
3. Read progress-row status.
4. Stalled/paused → branching-arrow; verify Working.
5. Achieved → new INTENDED → Set Goal / `/goal` → send → audit.
6. Working + need steer → paste → → Steer → composer cleared.
7. ABORT if text in terminal.
8. PROMPT_AUDIT + screenshots.
9. Confirm `RESULT.txt` or `BLOCKER.txt` exists in the job workdir.

## Always
Never invisible `codex exec` for watched Goals. ≤4K. Mac Mini only. Audit every inject.

---
name: Bob Codex queue inject
description: >-
  use this when Bob needs to steer, resume, Set Goal, or follow-up a
  Jeff-watched ChatGPT Codex / Astra thread on the Mac Mini without Jeff pasting
  — includes Goal progress-row controls and resource-discipline
---
---
name: Bob Codex queue inject
description: >-
  use this when Bob needs to steer, resume, Set Goal, or follow-up a
  Jeff-watched ChatGPT Codex / Astra thread on the Mac Mini without Jeff pasting
  — includes Goal progress-row controls and resource-discipline
---
# Bob Codex queue inject (Mac Mini)

## When
Jeff is watching a named ChatGPT.app / Codex Goal on the Mac Mini and Bob must inject a follow-up, resume, Set Goal, or steer without paste — and must use Astra/Codex resources correctly (Jeff 2026-09-22: know the controls; use them well; keep getting better).

Pair with [Codex Goal mastery](sand-workflow:codex-goal-mastery) (what to write) and [Codex prompt audit](sand-workflow:codex-prompt-audit) (prove it landed).

## Machine
Only `Jeffs-Mac-mini.local` (`machineId` `53abfd07-b321-433b-b068-55620c6c756d`) until Jeff reopens other Macs.

## Resource discipline (hard)
1. **One coding lane** on a checkout: Astra/Codex OR Cloud — never dual-lease the same WebJam tree.
2. **Astra does the heavy coding**; Bob does light OCR/unstick/audit.
3. **Prove Working / Pursuing goal** before claiming inject done. Paste alone is never done.
4. **After "Goal achieved"** → write a **new** ambitious clean Goal (six-part). Do not thrash resume.
5. Prefer fewer, sharper Goals over rapid CONTINUE spam. If vague mid-run: tighten Goal, don’t spam.

## Goal progress-row controls (desktop)
Docs: https://learn.chatgpt.com/docs/long-running-work — progress row pause / resume / edit / clear.

| UI state | Correct action |
| --- | --- |
| **Goal stalled / paused** | Click the **branching-arrow** (fork) next to the status chip — Jeff’s unpause control. |
| **Goal achieved** | Clear composer; **Set Goal** / `/goal` fresh six-part contract; blue-send. Composer Goal text must **start with `/goal`**, then press Return/send. |
| **Working / Thinking / Pursuing** | Healthy — quiet unless steering. |
| **Error in message stream** | One Retry only; still dead after ~90s → BLOCKER + failover to local_cursor/Claude; no STEER spam (2026-09-26). |
| Queued follow-up while turn live | Paste into **Do anything**, then click **`→ Steer` on the queued-message row** (arrow + word Steer at the right of the truncated queue text). That row sits above the progress bar. |
| Fresh idle composer | Paste INTENDED; blue **send** beside Astra chip (OCR x>900 → right ~1763,1317; else ~590,1317). |

### Queued Steer — exact target (Jeff 2026-09-22)
When a Goal is **Pursuing/Working** and a follow-up is queued, submission is the **`→ Steer` affordance on the queued-message row** — not the progress-row pause/resume/play-looking control, not the blue Stop (white square), and not idle blue Send. Progress row = lifecycle only.

Automation: activate the large ChatGPT window (not the tiny overlay), crop the lower band, OCR for `Steer` on the same row as the queued text, one CGEvent click at that box center (`ocr_all_bin` + `steer_only.swift` pattern). Verify the queue row disappeared/changed and Goal remains Pursuing before claiming success. Avoid recursive AX `entire contents` dumps.

### Anti-patterns
- `/goal resume` glued to CONTINUE → **Replace current goal?** (Cancel).
- Opening stalled chip before Steer.
- Claiming sent while composer still shows text or queue row still shows `→ Steer`.
- Clicking Stop / progress-row play when you meant queued Steer.
- Shell without `machineId`.
- Dual-lease Cloud + Codex.

## Paste target
**Do anything** / Goal composer **ABOVE** terminal. Never the shell.

## Recipe
1. Screenshot; confirm thread.
2. Read progress-row status.
3. Stalled/paused → branching-arrow; verify Working.
4. Achieved → new INTENDED starting with `/goal` → Return/send → audit.
5. Working + need steer → paste → click **`→ Steer` on queue row** → queue cleared.
6. ABORT if text in terminal.
7. PROMPT_AUDIT + screenshots.

## Always
Never invisible `codex exec` for watched Goals. ≤4K. Mac Mini only. Audit every inject.

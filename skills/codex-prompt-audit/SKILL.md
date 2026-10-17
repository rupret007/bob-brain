---
name: Codex prompt audit
description: >-
  use this when drafting, pasting, or reviewing any Codex Goal / CONTINUE /
  Steer text — verify intended body landed, strip chat wrappers, score six-part
  quality, prove active Goal in DB, and improve the next prompt
---
# Codex prompt audit (Goal + CONTINUE)

## When
Before and after every Codex Goal create, Set Goal, CONTINUE, or Steer inject — including when Jeff pastes a Bob-drafted prompt. Also before Claude Goal/CLI injects when Bob is conducting (same hygiene).

First read [Codex Goal mastery](sand-workflow:codex-goal-mastery) for official six-part contract, when-not-to-use-Goals, and lifecycle.

## Intent vs wrapper
The **intended prompt** is only the contract body that starts with a marker like `WEBJAM_CLOSEOUT_…` / `CONTINUE …` / `JEFF_YES …`.

**Never** include Bob chat chrome in the Goal objective or Do-anything field:
- "Paste this into Codex…" / "Paste only the block below…"
- "Prefer a fresh thread…"
- "Yes — use the **Bob The Bot** ChatGPT project…"
- markdown fences or "Paste this into a **new Goal**…"

Those belong in the chat message to Jeff, not in Codex.

## Quality bar (best prompt — self-improve)
Every INTENDED body must earn a short `PROMPT_QUALITY.txt` score (pass/fail each):
1. **Marker-first** — first line is the marker; no chrome above it
2. **≤4K** — prefer ≤3K when possible
3. **Six-part contract** (OpenAI cookbook): Outcome, Verification surface, Constraints/Holds, Boundaries, Iteration policy, Blocked stop — for Extra High / Ultra / long-horizon
4. **Worth-building gate** — thin leftover vs overbuild; say what NOT to invent; Goal bigger than one prompt, smaller than open backlog
5. **Exact paths + SHAs** — canonical checkout, base tip, coord issue
6. **Holds explicit** — parked PRs, Pages, feel, spend, lease stacking
7. **Done = evidence** — tests named, tip SHA, PRE_KAREN / WRAP shape; evidence decides complete, not vibes
8. **One lane** — no cross-repo pile-on; no Cloud+Codex dual-lease

If status goes vague mid-run: **tighten Goal** (next checkpoint + proving command + pause condition) instead of CONTINUE spam.

If any quality check fails, rewrite INTENDED before inject. After WRAP or a weak agent turn, add one line to `PROMPT_LESSONS.md` in the inject folder (defect → next-prompt fix) and fold durable fixes back into this skill.

## Live Goal proof (required — lesson 2026-09-13)
Cmd+Return / composer clear / a short agent reply is **NOT** success.
A CONTINUE that opens `codex-auto-review` / compaction-only sessions is **NOT** a pursuing Goal.
**PASS only if** after inject:
1. `sqlite3 ~/.codex/goals_1.sqlite` shows `status='active'` for the thread, **and**
2. `objective` starts with the marker, **and**
3. UI shows **Pursuing goal** / Working (screenshot), **and**
4. Jeff can open the same named ChatGPT.app thread.
If Save/Set Goal automation no-ops, stop and ask Jeff to Save — do not write STEERED=PASS.

## Pre-inject checklist
1. Write `INTENDED.txt` = marker + contract only (≤4K). No paste instructions.
2. Write `PROMPT_QUALITY.txt` (8 checks). Fix until all pass.
3. Hash or byte-length INTENDED.
4. Confirm target thread id + window title (WebJam vs StoryBoard vs Fantasy vs other).
5. Confirm paste target is **Do anything** / Goal composer ABOVE terminal — never shell.
6. Prefer Bob Mini inject of INTENDED only (Jeff Save for Set Goal if automation Save no-ops).
7. Read progress-row state first (Working / stalled / achieved) — see [Bob Codex queue inject](sand-workflow:bob-codex-queue-inject).

## Post-inject verify
1. Re-read what landed (goals DB + UI).
2. Assert objective/CONTINUE **starts with the marker**.
3. Fail if wrapper phrases appear before the marker.
4. Write `PROMPT_AUDIT.txt`: intended length, landed length, quality score, **active_goal bool**, pass/fail, one-line fix for next time.

## Self-improvement loop
On every FAIL, near-miss, or mediocre agent outcome:
1. Note defect class (wrapper leak, fake STEERED, weak outcome, missing hold, wrong thread, terminal paste, missing Steer, marker drift, >4K, vague verification, resume-on-achieved thrash).
2. Fix the **next** INTENDED template immediately.
3. If live Goal objective is polluted: clean Set Goal when Jeff can Save; else CONTINUE "authoritative contract is MARKER onward."
4. Keep lessons in the inject RESULT folder; update this skill when a defect repeats twice.
5. Jeff 2026-09-22: keep researching and baking better Codex/Goal practice into skills — never stop improving the conductor.

## Draft hygiene for Jeff-paste Goals
- Lead with: **Paste only the block below (marker first). Do not paste this chat sentence.**
- Contract alone inside one fence; setup outside.
- Prefer Bob inject so Jeff never pastes.

## Always
- Never invisible `codex exec` for watched Goals.
- Steer when a turn is already in progress.
- Mac Mini only until Jeff reopens other machines.
- Jeff 2026-09-13: audit every prompt; self-improve continuously; never claim Codex running without active goals DB proof.

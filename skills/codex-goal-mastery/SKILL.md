---
name: Codex Goal mastery
description: >-
  use this when drafting, injecting, steering, or auditing Codex / ChatGPT Goal
  prompts (Astra Ultra) — official six-part contract, lifecycle controls, when
  not to use Goals, and Bob conductor discipline
---
# Codex Goal mastery

## When to use this
Use whenever drafting, injecting, steering, pausing, resuming, or auditing a Codex / ChatGPT desktop Goal (Astra Ultra, Extra High, etc.) — especially on Jeff’s Mac Mini watched threads.

## Sources (official)
- OpenAI cookbook: Using Goals in Codex — https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex
- Use case: Follow a goal — https://developers.openai.com/codex/use-cases/follow-goals
- ChatGPT Learn: Long-running work — https://learn.chatgpt.com/docs/long-running-work

## Goal vs one-off prompt
- **Prompt:** ask → work → result → wait.
- **Goal:** work → check evidence → continue or complete. Durable thread-scoped objective.
- Use a Goal when the finish line is clear but the path needs multi-turn discovery (perf, flaky tests, migrations, multi-step polish, evidence-backed research).
- **Do NOT use a Goal** for one-line edits, simple explanations, short reviews, or vague “make it better” with no audit surface.

## Six-part contract (write every Ultra / long-horizon Goal this way)
1. **Outcome** — what must be true when done (end state, not activity).
2. **Verification** — named tests, benchmarks, artifacts, commands, PR state that prove it.
3. **Constraints** — what must not regress / holds.
4. **Boundaries** — which repo, paths, tools, resources are allowed.
5. **Iteration** — how to choose the next experiment after each attempt (checkpoints + short progress log).
6. **Blocked stop** — when to stop and what input unlocks progress.

Template:
`/goal <end state> verified by <evidence> while preserving <constraints>. Use <boundaries>. Between iterations, <next-action rule>. If blocked, report attempted paths, evidence, blocker, next input.`

Size: bigger than one prompt, smaller than an open-ended backlog. Narrow enough to audit, broad enough to choose next actions.

## Lifecycle controls
Slash (CLI / when available): `/goal` view · `/goal <objective>` set · `/goal pause` · `/goal resume` · `/goal clear` · `/goal edit` (TUI).
Desktop ChatGPT app: progress row above composer — pause / resume / edit / clear. Jeff’s Mini: **branching-arrow (fork) icon** next to Goal stalled/paused chip unpauses; after **Goal achieved**, set a **fresh** Goal — do not thrash resume. Follow-ups while running: paste Do anything then **→ Steer**. Idle send: blue arrow beside model chip.
Side chat for status without interrupting. Pause before losing connectivity; resume when ready.
Goals do not expand sandbox/approvals; model cannot pause/resume/clear — user/system owns those.

## Completion rules (how Codex thinks)
- Complete only when **current evidence** proves every requirement (files, commands, tests, artifacts) — not intent or memory.
- Budget exhausted ≠ complete; summarize and stop.
- `blocked` only after the **same** blocker for ≥3 consecutive goal turns; then mark blocked, don’t loop.
- Plan-only turns do not auto-continue; no-tool continuation suppresses the next auto-continue (anti-spin).
- Keep full objective intact; do not redefine success to a smaller easier task.

## Conductor discipline (Bob)
- One coding lane per checkout (Astra OR Cloud OR `local_cursor` — never dual).
- Astra codes; Bob injects/audits/unsticks lightly. **No Grok worker** until ~6-day reset (Jeff 2026-09-26).
- Marker-first INTENDED; no chat wrappers; ≤4K (prefer ≤3K).
- Prove Pursuing/Working + goals DB when possible before claiming done.
- If status goes vague: **tighten the Goal** (next checkpoint + proving command + pause condition), don’t spam CONTINUE.
- **Stream error recover:** “Error in message stream” → one Retry → still dead → BLOCKER + failover to `local_cursor`/Claude; never STEER a dead stream (2026-09-26 WebJam polish).
- Prefer `/plan` then `/goal` when outcome is unclear.
- Compact status asks: checkpoint, verified, remaining, blocked?

## Pair with
- [Bob Codex queue inject](sand-workflow:bob-codex-queue-inject) for Mini UI mechanics.
- [Codex prompt audit](sand-workflow:codex-prompt-audit) for every inject.

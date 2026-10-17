---
name: Claude Code mastery
description: >-
  use this when drafting, injecting, or steering Claude.app / Claude Code for
  Jeff — explore-plan-verify, CLAUDE.md, /goal, Pro Sonnet spend rules, and
  long-running handoffs
---
# Claude Code mastery

## When
Drafting, injecting, or steering Claude.app / Claude Code on Jeff’s Mini (or Cloud Fable backup). Pair with [Multi-LLM stack mastery](sand-workflow:multi-llm-stack-mastery) and [Best LLM for the job](sand-workflow:best-llm-for-the-job).

Sources: https://code.claude.com/docs/en/best-practices.md · Anthropic long-running harnesses · Claude `/goal` generator/evaluator.

## Jeff spend (hard)
- Claude is **$20 Pro only**. Prefer **Sonnet 5** for overnight leftovers.
- **Fable 5 / 5.1** bill paygo — not included Pro. Only if Jeff wants that spend.
- If OAuth expired / READY_SONNET NO: Jeff re-login gate — don’t start paygo API overnight without yes.
- Claim `claude` lease; never dual-lease with active Codex/Cloud on same checkout.

## Core loop
**Explore → Plan → Implement → Verify.** Plan mode (`Shift+Tab` / `--permission-mode plan`) before multi-file or unclear scope. Skip plan for one-sentence diffs.

## Give Claude a check it can run
Tests, build exit code, linter, screenshot vs design. Prefer `/goal` completion condition (separate evaluator) or Stop hooks for unattended. Show evidence (output, command, screenshot) — not “done.”

## Long-running / multi-session
- One feature per session; **PROGRESS.md** handoff (`Done` / `In progress` / `Next` / `Notes`); read it first + `git log -10` + smoke test.
- Commit clean checkpoints; leave mergeable state.
- Initializer vs coding agent pattern for multi-context windows.
- Adversarial review in **fresh** subagent before calling good.
- `/clear` between unrelated tasks; after two failed corrections, clear and rewrite the prompt.
- Subagents for investigation so main context stays clean.

## CLAUDE.md
Concise (&lt;~200 lines). Only rules that prevent real mistakes. Exact commands, divergent conventions, gotchas. Skills for occasional domain knowledge. Prune when Claude ignores rules.

## Permissions
Allowlist trusted commands; sandbox when useful; auto mode for classifier-gated unattended. Avoid bypass except isolated VMs.

## Prompt shape
Specific files, constraints, patterns to copy, symptom + fix proof. `@` files, paste screenshots, allowlist docs URLs. Interview→SPEC.md for large features, then fresh session to implement.

## Not for
Vague “improve everything”; stacking on WebJam while Astra holds the lease; burning Fable overnight by default.

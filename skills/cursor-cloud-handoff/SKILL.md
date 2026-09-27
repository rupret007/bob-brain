---
name: Cursor Cloud handoff
description: >-
  use this when handing large coding or multi-file PR work to Cursor Cloud
  Agents from Bob — absorbed OpenClaw cursor_handoff rules with native Grok Bot
  Cloud Agents first
---
# Cursor Cloud handoff

## When
Use this when handing large coding / multi-file / PR work to Cursor Cloud Agents from Bob/Grok Bot — the absorbed replacement for OpenClaw’s `cursor_handoff` skill. Prefer native Grok Bot Cloud Agents tools; Integration CLI is fallback only.

## Prefer native tools
Use the Cursor CloudAgent actions: launch, list, get, watch, reply, cancel, dump, models. Do not ask Jeff for session keys or routing IDs.

## When to hand off
- Multi-file features, refactors, failing tests, branch/PR workflows, deep repo analysis
- Not for tiny shell one-offs, simple Q&A, or non-coding tasks

## Decision rules (from OpenClaw investment)
1. Prefer direct Bob/Grok work for small local low-risk tasks.
2. Hand off repo-heavy work to Cloud Agents.
3. Ambiguous analysis → read-only framing in the prompt.
4. Edit/implementation only when Jeff clearly wants code changes.
5. Never infer merge, Latest, tag, spend, or destructive git without Jeff.
6. One coding lease per checkout; one WebJam coding lane.
7. User-facing summaries stay product-level; raw tool jargon stays internal.
8. DRAFT PRs by default unless Jeff said otherwise.

## Intent templates
Pass a clear objective using one of these shapes in the Cloud Agent prompt:
- `code-review` — risks, test gaps, read-only
- `refactor` — behavior-preserving cleanup
- `release-notes` — user-facing notes from recent work
- `brief` — product/creative brief structure
Always include: objective, constraints, acceptance criteria, absolute checkout/repo URL, DRAFT-only unless told, and hard fences (no secrets, no auto-send, no gateway restart).

## Branch names
If Jeff names a branch, use it. Else prefer readable `cursor/<topic>-…` that the Cloud Agent creates.

## Fallback CLI (only if native blocked)
Optional: `scripts/cursor_openclaw.py` / handoff scripts from Bob `tools/` once vendored, or legacy `rupret007/Cursor-OpenClaw-Integration`. Always `--dry-run` first. Never treat CLI as a bypass of Jeff gates.

## Safety
- No secrets in prompts
- No andrea_sync / Telegram / Alexa sends from this path
- No OpenClaw gateway restart
- Report agent URL + PR URL + tip SHA as done evidence

## Done means
Agent launched or replied with clear goal, watch/register for completion, and Jeff only pinged for blockers / needs-yes / real advances.

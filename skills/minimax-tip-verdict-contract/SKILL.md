---
name: MiniMax tip VERDICT contract
description: >-
  use this when filing or scoring MiniMax tip critiques — final channel must be
  VERDICT-only; CoT-only is Eff E1 FAIL
---
# MiniMax tip VERDICT-only contract

Locked 2026-09-25 ~2:36 CT after R4 CoT flood.

## When
Any MiniMax tip / PR critique / BYOK critique that Bob or MiniMax Runner will score or act on.

## Rule
Final channel must be usable VERDICT text:
1. First line: `VERDICT: PASS` or `VERDICT: FAIL`
2. Then short Findings / Must-fix / CodeQ notes
3. No chain-of-thought, no think-blocks, no prompt restatement as the body

## Scoring
- Missing VERDICT after strip → Eff **E1 FAIL** (HTTP 200 alone is not enough)
- CoT-only → unparseable; do not merge or board-promote
- Prefer prompt: “Final answer only. Start with VERDICT:”

## Pair with
Full note: `/home/box/conductor/minimax-tip-verdict-contract.md`
Architecture: `/home/box/conductor/llm-work-now/architecture-delta-20260925-0236.md`


## Prompt hygiene (R5)
- No think-close / think-open tags in user prompts; compact prompts; tip-once after usable VERDICT.
- Pair: `/home/box/conductor/minimax-tip-verdict-contract.md`

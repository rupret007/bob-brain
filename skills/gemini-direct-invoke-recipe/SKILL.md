---
name: Gemini direct invoke recipe
description: >-
  use this when calling Google Gemini generateContent for harden stress —
  compact prompt + thinkingBudget≈128 + maxOut≥800 for heavy; light uses thinkingLevel=low
---
# Gemini direct invoke recipe (post-R8)

Never route Gemini through Cursor Cloud under spend wall. Use Google API ids only.

## Model pins
| Role | ID |
| --- | --- |
| Heavy | `gemini-3.1-pro-preview` (never bare `gemini-3.1-pro`) |
| Light | `gemini-3.8-flash` with `thinkingLevel=low` + maxOut≥256 |

## Heavy working recipe (R8 measured)
Long prompts burn MAX_TOKENS on thoughts (R8 r1: 3933 thoughts / 159 candidates).

```python
body = {
  "contents":[{"role":"user","parts":[{"text": compact_prompt}]}],
  "generationConfig":{
    "temperature": 0.1,
    "maxOutputTokens": 800,   # ≥800
    "thinkingConfig":{"thinkingBudget": 128}
  }
}
```

- **Compact prompt** — key fns + binding rule + markers; no full dump.
- **thinkingBudget≈128** — stops thought burn.
- **maxOut≥800** — room for ASSESS markers after thoughts.
- R8 r4: ASSESS_OK in ~7s with this recipe.

## Light recipe
```python
"generationConfig":{
  "temperature":0.1,
  "maxOutputTokens":512,
  "thinkingConfig":{"thinkingLevel":"low"}
}
```

## Binding reject (do not re-implement)
Do **NOT** tip/validate "add running guard to validate_llm_work_write".
`llm_work_running_reject_reasons` already returns `[]` when `status != "running"`.
False FIX = critique fail even if Stress pipe PASS.

## Markers
Heavy ends `ASSESS_OK` / `ASSESS_BLOCKED`. Light ends `LIGHT_OK` / `LIGHT_FAIL`.


## R10 — first-try ultra-compact (mandatory)
R9+R10 r1 still hit MAX_TOKENS on medium prompts even with thinkingBudget=128.
**First invoke** must use writer-snippet-only (~15 lines) + reject excerpt + markers. Save medium dumps for r2 only if ASSESS_PARTIAL with real content gap.


## Tip reviews (HARD — architecture 2026-09-26 ~8:12 PM CT)
Never hand-roll curl for tip Gemini. Truncated mid-sentence / missing `ASSESS_*` bodies are unusable.
1. Box: `/workspace/bin/gemini_tip_assess.py <prompt_file>`
2. Mini: `~/Documents/bob-overnight-inject/bin/review-tip-gemini.sh <prompt_file> [out.md]` (copies same helper)
3. Fail-closed: empty → exit 6; no `ASSESS_OK`/`ASSESS_BLOCKED` → exit 3. Retry raises `maxOutputTokens` (768→1536→2048) with `thinkingLevel=low`.
4. Pair with MiniMax tip path (`minimax_verdict.py` / `review-tip-minimax.sh`). Both required for tip critique.

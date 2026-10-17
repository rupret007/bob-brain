---
name: MiniMax BYOK work lane
description: >-
  use this when a cheap MiniMax BYOK honesty/critique pass is needed —
  prefer MiniMax Runner silent peer; Bob skill = capped one-shot fallback
---
use this when a cheap BYOK honesty/critique pass is needed on an open DRAFT or tip — MiniMax only, never Cursor Cloud, capped volume. Prefer **MiniMax Runner** SILENT_CAPPED_PEER for standing critiques; this skill remains policy + Bob one-shot fallback. Never print the key.

# MiniMax BYOK work lane

## Role
Low-cost critique/docs lane. Rank 1: **MiniMax Runner** owns silent capped critiques off Jeff’s path. Bob may delegate to that peer or run this skill inline for a true one-shot.

## Use for
- PR / tip honesty (leftovers, false CI claims, fence language)
- Bounded ≤1 page artifacts under `/home/box/conductor/llm-work-now/`
- Second-opinion notes handed to the coding lease
- Structured lyrics / setlist packaging via text models when hosted Music/Lyrics APIs are locked

## Cap (hard)
- **Max 1 active tip SHA** at a time
- **One critique per tip SHA** — no regenerate-same-tip
- Prefer the current rank-1 tip (e.g. WebJam) when its CI is moving
- Otherwise at most one secondary DRAFT critique; apply/discard before starting another
- No tip floods; `auto_pulse=false` unless a quiet capped peer pulse owns it
- Peers never DM Jeff — board + Bob only

## Invoke helper (HARD — 2026-09-26 ~19:50 CT)
Tip / critique reviews **must** go through the verdict helper — never hand-rolled `curl` / ad-hoc Python that leaves `<think>`-only bodies (recent review-1912 CoT-only = unusable).
1. **Box (preferred):** `/workspace/bin/minimax_verdict.py <prompt_file>`
2. **Mini:** `~/Documents/bob-overnight-inject/bin/review-tip-minimax.sh <prompt_file> [out.md]` (same helper copied under `bin/minimax_verdict.py`)
3. Exit 3 from helper = no VERDICT after retries → record UNPARSEABLE / Eff E1 FAIL; tip-once (no same-SHA redo).
4. Do not invent PASS from HTTP 200 alone.

## Call pattern
1. Confirm `MINIMAX_API_KEY` present (never print it)
2. Confirm balance is not empty — chat returns **HTTP 402** `insufficient_balance_error (1008)` until Jeff recharges; **do not invent success**
3. Pin models from live `/v1/models` catalog (M-series only):
   - **Default critique:** `MiniMax-M2.7` (prefer over highspeed for $)
   - **Cheap/fast critique:** `MiniMax-M2.7-highspeed` (matches env `MINIMAX_MODEL_FAST`)
   - **Hard judgment / long boards:** `MiniMax-M3` (matches env `MINIMAX_MODEL_COMPLEX`)
4. Write `minimax-YYYYMMDD-HHMM-<slug>.md` + update llm-work-now MiniMax row with model id
5. Do not push code, merge, send, or spend

## Model notes (2026-09-25 live catalog)
- **`MiniMax-Text-01` is obsolete** — not in live `GET /v1/models`; do not pin
- Live text ids: `MiniMax-M2`, `M2.1`, `M2.1-highspeed`, `M2.5`, `M2.5-highspeed`, `M2.7`, `M2.7-highspeed`, `M3`
- **Hosted Music gated:** `music-3.0` / lyrics → **HTTP 410** (status 2153) for this key (new-user lockout since 2026-08-20); do not call until Jeff/support unlocks; prefer text lyrics packaging or MiniMax Audio / self-host Music3
- **Empty balance blocks chat:** 402 until Jeff recharges Open Platform balance — report failure honestly; never fabricate a completed critique
- Guide: `/home/box/conductor/minimax-models-guide-20260925.md`

## Rank 1 hardenings (2026-09-25 ~1:01 AM CT retro)
- Runner status exact **`SILENT_CAPPED_PEER`**; never DM Jeff; board + Bob only with **`priority:false`** FYI default.
- **33 tips dated 2026-09-25** proved tip flood — hard stop: one critique per tip SHA, then idle; no Text-01 (use M2.7 / M3).
- If critique finds PR body tip lag or generated `status.json`/`index.html` churn, file LEFTOVER for Bob — do not push/merge.

## Hard fences
- Not a WebJam coding lease — **Codex remains WebJam coding sole**
- No secrets / customer / Cisco live data
- hold_final_build / Jeff gates unchanged
- Never print API keys

## Tip parseability (HARD — 2026-09-25 ~2:00 AM CT)
M2.x **cannot disable thinking**. CoT often fills `content`; strip → empty → tip unusable.

### Prompt contract (every tip/critique)
1. System+user must require a final line **outside** think/CoT exactly one of:
   - `VERDICT: PASS`
   - `VERDICT: FAIL`
   - `VERDICT: PASS-with-LEFTOVER`
2. Instruct: "After private reasoning, emit the VERDICT line and short bullets in plain text. Do not put VERDICT only inside think blocks."
3. Call pattern (learned Round3 probe 2026-09-25 ~2:00 CT):
   - **Preferred for tips:** OpenAI chat **without** `reasoning_split` + strip `<think>…</think>` from `content`, then require `VERDICT:` on remaining text (Bob#30 + Round3 attempt A worked).
   - Optional `reasoning_split: true` **only if** you verify `content` is non-empty and contains `VERDICT:`. Round3 showed split can put **everything** in `reasoning_content` with `content=""`, which is still UNPARSEABLE — never accept VERDICT only from reasoning fields.
   - Docs: https://platform.minimax.io/docs/api-reference/text-openai-api

### Parse / fail-closed
1. Strip `<think>…</think>` / CoT wrappers from `message.content`.
2. Require regex `^VERDICT:\s*(PASS|FAIL|PASS-with-LEFTOVER)\b` on remaining text (multiline).
3. **Empty-after-strip OR no VERDICT match = UNPARSEABLE = lane FAIL.** Record HTTP + reason. **Tip-once** — do not regenerate same tip SHA.
4. Always retain raw pre-strip body in the artifact for audit (miss on dashboard #57 `d3f5ddc`).
5. Never invent PASS from runner notes when model VERDICT is missing.

Evidence: #57 UNPARSEABLE CoT-only; Bob#30 PASS with outside-think VERDICT.

## Status (2026-09-25 ~1:56 AM CT)

- Use **Subscription / Token Plan** key (`sk-cp-…`) from Bob/MiniMax Runner `.minimax_api_key` or `$MINIMAX_API_KEY` after `source ~/.minimax_env`.
- Open Platform `sk-api-…` was empty (402); Coding Plan credits are the live bucket.
- Still report real HTTP failures honestly; never invent tip success.

## Contract SoT (2026-09-25 ~2:36 CT)
`/home/box/conductor/minimax-tip-verdict-contract.md` — final channel VERDICT-only; CoT-only = Eff E1 FAIL. Bob: use `update_state` if peers need this path.


## Prompt hygiene (R5 — 2026-09-25 ~02:47 CT)
- Never put literal think-close tags (closing `</` + `think>` pair) or open think tags in **user** prompts — confuses M2.x into false empty-input.
- Prefer compact tip prompts; tip-once after usable FINAL_CHANNEL VERDICT (no same-SHA redo).
- Keep strip + `^VERDICT:` fail-closed; CoT-only = UNPARSEABLE = Eff E1 FAIL.


## Retry / fail-closed (R6→R7 — 2026-09-25 ~02:56 CT)
- **r1 CoT-only** → one compact retry (raise max_tokens / stronger FINAL-first preamble; never think-close tags in prompts).
- **r2 CoT-only** → lane **FAIL-closed**, **no r3**. Record finish/empty-after-strip reason.
- **Tip-once** after usable FINAL_CHANNEL `VERDICT:` — no same-SHA regenerate.
- Contract SoT: `/home/box/conductor/minimax-tip-verdict-contract.md`

## Fail-closed empty verdicts (ops 2026-09-26 ~20:00 CT)
Mini `review-tip-minimax.sh` rejects empty bodies (exit 6) and missing VERDICT (exit 3). Never leave 0-byte `reviews-out/*-minimax.md` as success — re-run `/workspace/bin/minimax_verdict.py`.

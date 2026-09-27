---
name: No Cursor waste routing
description: >-
  use this before launching any model fill to avoid burning Cursor Other Models
  when BYOK, Mac Mini, or local Cursor Composer can do the job
---
# No Cursor waste routing

## When
Use before launching any model fill (Codex, Claude, Gemini, MiniMax, Grok, Cursor Cloud, local Cursor) — especially under GO MAX, keep-pressing, or the highest-bar harden loop.

## Preference order
1. BYOK direct (`byok`): MiniMax API, Gemini API (`GEMINI_API_KEY`) for work that does not need a Cursor VM.
2. Mac Mini goal paste (`mini`): ChatGPT Codex and Claude apps (Jeff’s OpenAI/Anthropic plans).
3. LOCAL Cursor on Mini (`local_cursor`): desktop Cursor app Composer / local agent — Cursor Models/Composer pool (separate from Cloud Background Agents). **Always** `cursor agent --model composer-2.5 -f --trust -p …`. Empty output = FAIL; retry once with `--workspace`.
4. Cursor Cloud Background Agents (`cloud`): last resort only — need Cursor-hosted checkout AND spend headroom. Banned under BLOCKED_SPEND_WALL. **Harden-loop stress: Cloud BA count must be 0.**

## Bans
- Do not route Gemini through Cursor Cloud when the Gemini API key can do the job.
- Do not spray Claude/Gemini/Grok Cloud to keep lanes “busy.”
- Tip critique stays MiniMax BYOK.
- Do not conflate local Cursor Composer (`local_cursor`) with Cloud Background Agents (`cloud`).
- Do not use Bob/Grok as a stress or heavy coding lane.
- **Grok worker ban (Jeff 2026-09-26 ~11:55 AM CT):** zero Grok coding/worker fills (Bob chat heavy work + Cloud `grok-*`) until ~6-day Grok usage reset (~2026-10-02). Conductor/OCR/unstick only. Prefer Codex/Claude/MiniMax/Gemini/`local_cursor`.
- `local_cursor` is an **active** coding lane (Jeff ~11:56 AM CT), not a spare — use it when Codex/Claude thin or stream-blocked; still one WebJam coding lease.
- If Cloud launch refuses on usage/on-demand wall: stop Cloud fills; fall back to Mini + BYOK + local Cursor; no retry spam.

## Harden-loop note
See `/home/box/conductor/harden-loop-pass-criteria.md` for ruthless PASS/FAIL checks.

## Evidence
Record path on the board: `mini` | `byok` | `local_cursor` | `cloud` for every assignment.

## Gemini direct pins (Google API ids — 2026-09-25 ~2:00 AM CT)
- Heavy: `gemini-3.1-pro-preview` (never bare `gemini-3.1-pro` — 404 on generateContent)
- Light: `gemini-3.8-flash` with `generationConfig.thinkingConfig.thinkingLevel=low` and `maxOutputTokens≥256`
- Fallback: `gemini-2.5-flash` / `gemini-2.5-pro`
- Source `~/.gemini_env` (`GEMINI_MODEL_HEAVY/LIGHT`). Cloud Cursor labels ≠ Google API ids — do not pass Cloud names to Google AI.
- Docs: https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview · thinking: https://ai.google.dev/gemini-api/docs/generate-content/thinking
- Resolve note: `/home/box/conductor/llm-work-now/gemini-model-id-resolve-20260925-0200.md`

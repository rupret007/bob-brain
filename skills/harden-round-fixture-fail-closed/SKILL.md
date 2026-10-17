---
name: Harden round fixture fail-closed
description: >-
  use this when opening/closing overnight harden stress rounds so Gemini/MiniMax
  never FileNotFound and Stress PASS is never rubber-stamped
---
# Harden round fixture fail-closed

Use with the overnight multi-LLM harden loop (assess→research→implement→5m stress).

## Problem this prevents
Copying `write_harden_window.py.txt` / `reject-reasons-fn.py` from `PREV` round breaks the chain (seen R90+): once one round lacks fixtures, every later round Gemini/MiniMax crashes with `FileNotFoundError` while close scripts still stamp Stress PASS.

## Open (every round)
1. Keep canonical fixtures at `/home/box/conductor/llm-work-now/harden-fixtures/`.
2. **Refresh from live dashboard each open** (not from PREV):
   - copy `bob-ops-dashboard/write_harden_window.py` → `write_harden_window.py.txt`
   - extract `llm_work_running_reject_reasons` from `board_meta.py` → `reject-reasons-fn.py`
3. Copy fixtures into the new `harden-stress-rN-*` OUT dir.
4. **Fail closed** if either fixture file is missing/empty before launching invokes.
5. **K9 wrappers:** `harden-round-box.sh` exits **non-zero** (`WRAPPER_FAIL`) if `harden-fixtures/invoke-wrappers/{invoke_gemini_heavy,invoke_gemini_light,invoke_minimax}.py` are missing/empty — before any invoke.
6. Fire Gemini heavy + light + MiniMax BYOK (`sk-cp`) in parallel; Mini inject texts under `OUT/mini-inject/`.

Script: `harden-round-box.sh`.

## Close (every round)
1. Score from **log evidence**, never hardcode ASSESS_OK:
   - Gemini heavy needs `ASSESS_OK` (log or `.md`)
   - Gemini light needs `LIGHT_OK`
   - MiniMax needs a usable `VERDICT:` (or honest FAIL) and **no Traceback**
2. Any Traceback in those three logs → **Stress FAIL**.
3. Mini Working grade STRONG|PARTIAL required for Eff PASS on the Working-proof track; WEAK/PENDING → Eff FAIL.
4. Round card one-liner must say what got better for Jeff (honesty catch counts).

Script: `harden-round-close.sh`. Quality loop: `overnight-quality-loop.sh` (FAIL_CLOSED=1).

## Anti-thrash
- Do not re-roll identical MiniMax tips after two fails — escalate the VERDICT contract skill.
- Reject already-fixed research FIXes (running-guard invent on `validate_llm_work_write`).
- No WebJam Latest / Barker / Cloud BA during time-floored harden.

## Evidence-gated close (R126 — 2026-09-25 ~07:20 CT)
Overnight R90–R105 wrote Stress PASS while Gemini/MiniMax crashed on missing `write_harden_window.py.txt` / `reject-reasons-fn.py` after PREV-chain break.

**Fail-closed:** before scoring Stress PASS, assert invoke fixtures exist and lane logs show HTTP/VERDICT/ASSESS markers. Missing fixture or crash = **Stress FAIL**; do not close as PASS. Pair with [Anti-rubber-stamp research gate](sand-workflow:anti-rubber-stamp-research-gate).

## Canonical invoke wrappers (R126)
Use `/home/box/conductor/llm-work-now/harden-fixtures/invoke-wrappers/{invoke_gemini_heavy,invoke_gemini_light,invoke_minimax}.py` — **not** PREV/r11 templates.
`harden-round-box.sh` copies these each open. Override topic via `OUT/assess-topic.txt` (anti-rubber-stamp).

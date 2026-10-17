---
name: Anti-rubber-stamp research gate
description: >-
  use this when harden/research rounds repeat the same OPEN residual or Stress
  PASS without fixtures — stop metronome; change topic or fail-closed
---
# Anti-rubber-stamp research gate

Locked 2026-09-25 ~07:20 CT after overnight: **42** Gemini-heavy notes still OPEN invent-running-guard; R90–R105 Stress PASS while invoke fixtures missing.
Mechanical close enforcement (K8) added 2026-09-25 ~08:01 CT.

## Rules
1. **Same OPEN / REJECT residual ×3 consecutive rounds** → do **not** re-ask the model the same BINDING question. Change assess topic to a *new measured hole*, or STOP the metronome.
2. **Mechanical OPEN×3 (K8)** — `harden-round-close.sh` hashes the last 3 `gemini-heavy.md` `OPEN:` lines (sha256 of normalized text). If identical → **usefulness FAIL**, writes `/tmp/harden-openx3-stop.txt`, exits **non-zero**, and **must not open R+1** (`harden-round-box.sh` refuses while the latch exists; `overnight-quality-loop.sh` breaks). Manual clear: `rm /tmp/harden-openx3-stop.txt` only after a new measured topic is on disk.
3. **Missing stress fixtures** (`write_harden_window.py.txt`, `reject-reasons-fn.py`, invoke wrappers) → round is **Stress FAIL** / close blocked. Never rubber-stamp ASSESS_OK or Stress PASS.
4. **Blank Jeff-visible gain** on the round card (“What got better for Jeff?”) → usefulness **FAIL** even if Stress PASS.
5. **Already-shipped FIX** (e.g. `validate_llm_work_write` → `llm_work_running_reject_reasons`) → BINDING REJECT inventing it again; put REJECT snippet in the prompt so the lane cannot “rediscover” it as FIX.
6. **REJECT invent-running-guard auto-prepend (K10)** — canonical `harden-fixtures/invoke-wrappers/invoke_gemini_heavy.py` always prepends BINDING: do **not** invent a running-guard FIX on `validate_llm_work_write` (covered by `llm_work_running_reject_reasons`). Default `OUT/assess-topic.txt` from `harden-round-box.sh` carries the same REJECT. Do not strip these on copy.
7. After **two consecutive evidence-gated Stress+Eff PASS** and no new measured hole → prefer finish-out / owner-reorder over another identical lap.

## Pair with
- [Harden round fixture fail-closed](sand-workflow:harden-round-fixture-fail-closed)
- [Conductor self-improvement loop](sand-workflow:conductor-self-improvement-loop)
- Exit bar usefulness + efficiency rules

## Invoke topic override
Write a *new* measured hole into `OUT/assess-topic.txt` before firing wrappers. Default topic forbids invent-running-guard thrash.

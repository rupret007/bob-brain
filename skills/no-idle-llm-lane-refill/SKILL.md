---
name: No-idle LLM lane refill
description: >-
  BURST ONLY + anti-waste: use only when Bob sets go_max AND spend headroom
  exists; prefer Lane peer; paused under BLOCKED_SPEND_WALL; no Cloud spray
---
**PAUSED under spend wall.** Use only during an explicit GO MAX / GO_MAX_SECONDARY burst after Bob sets `cloud_fills_mode=go_max` **and** Cloud headroom exists. Otherwise use [Priority-aware lane refill](sand-workflow:priority-aware-lane-refill) / [Priority lane refill](sand-workflow:priority-lane-refill) / [No Cursor waste routing](sand-workflow:no-cursor-waste-routing). Prefer **Lane Dispatcher** (SILENT_CAPPED_PEER) off Jeff’s chat path. Do **not** re-enable noisy no-idle every 20m onto Bob.

# No-idle LLM lane refill (burst only — anti-waste)

Idle-is-a-defect applies **only** when `cloud_fills_mode=go_max` and Jeff/Bob asked for a burst **and** spend headroom exists.

**`BLOCKED_SPEND_WALL`:** treat this skill as **paused**. Do not launch Cursor Cloud (including Gemini Cloud). Throughput = MiniMax BYOK + Gemini API direct + Mac Mini Codex/Claude paste + **LOCAL Cursor Composer/agent** (`local_cursor`, `cursor agent -f --trust`) + Actions CI.

When in burst mode **with headroom**:
1. Explicit model pins + path tag (`mini`|`byok`|`local_cursor`|`cloud`) on every assignment
2. One lease per repo; one WebJam coding lane max
3. Show Night PARKED unless Jeff reopens
4. Cancel duplicates on same repo/goal
5. Record model ids on the Work-now board
6. Gemini via **direct API** (`GEMINI_API_KEY`) for light/heavy secondary — **not** Cursor Cloud `gemini-*` by default
7. Never DM Jeff from the peer; board + Bob only
8. Never default-spray Cloud to keep models busy

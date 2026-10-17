---
name: Multi-LLM stack mastery
description: >-
  use this when choosing or driving any of Jeff’s models — Codex/Astra, Claude,
  Grok, Gemini, MiniMax — conductor rules, WebJam-first refill, and craft routing
---
# Multi-LLM stack mastery

## When
Use whenever choosing, launching, steering, or auditing any of Jeff’s models: **Codex/Astra (ChatGPT)**, **Claude**, **Grok (this Bot + Cloud)**, **Gemini**, **MiniMax**. Pair with [Best LLM for the job](sand-workflow:best-llm-for-the-job), [Codex Goal mastery](sand-workflow:codex-goal-mastery) / [Claude Code mastery](sand-workflow:claude-code-mastery), [Conductor self-improvement loop](sand-workflow:conductor-self-improvement-loop), [Multi-LLM stack smoke test](sand-workflow:multi-llm-stack-smoke-test), [MiniMax BYOK work lane](sand-workflow:minimax-byok-work-lane), and [Priority-aware lane refill](sand-workflow:priority-aware-lane-refill).

Jeff 2026-09-24: max the stack concurrently when mode allows; one WebJam coding lane; Jeff owns merge/tag/Latest/spend/feel.
Jeff 2026-09-25 Rank 1 (**Thin Front Door + Silent Parallel Specialists**): Bob stays thin Jeff-facing conductor + sole `cloud_fills_mode` writer. **Lane Dispatcher** and **MiniMax Runner** stay **silent capped peers** (not folded onto Bob’s Jeff-turn queue). **Band Desk** = named on-demand. Prefer WebJam-first; GO MAX = Bob-gated burst / GO_MAX_SECONDARY only — never standing.

## Conductor division (Rank 1)
| Role | Who |
| --- | --- |
| Front door / conductor / mode writer | **Bob** (thin) |
| Lane refill | **Lane Dispatcher** SILENT_CAPPED_PEER — board + Bob-only; never DM Jeff. Bob may delegate; skills = policy / one-shot fallback |
| MiniMax critiques | **MiniMax Runner** SILENT_CAPPED_PEER — max 1 active tip SHA; one critique per tip SHA; no tip flood. Bob skill = API fallback |
| Band desk | **Band Desk** NAMED_ON_DEMAND when StoryBoard / RadDad / Wildflower live; Show Night **PARKED** |
| Ship gate | **Karen** (peer, always) |
| Messages wire | **Andrea** (peer, always) |

Peers never DM Jeff. Comms = board + Bob-only. Do **not** fold long refill/critique loops onto Bob chat (Jeff-latency gate). Stack Ops is channel-only. Bob owns policy + single `cloud_fills_mode` writer. SLA: `/home/box/conductor/rank1-silent-specialists-sla.md`.

## Fill policy (critical)
- Default: **WebJam-first** (`cloud_fills_mode=webjam_focus`). Rank-1 product (WebJam #155) gets sole coding capacity until Jeff-testable or Jeff-gated.
- **GO MAX / GO_MAX_SECONDARY** = Bob-gated burst after rank-1 is green or waiting only on Jeff — free leases, explicit model pins, one lease/repo. Never a standing identity. Still **one WebJam coding lane**.
- Idle is **not** a standing defect requiring Bob metronome refill. Lane owns quiet refill pulse; do **not** re-enable noisy no-idle every 20m on Bob.
- [No-idle LLM lane refill](sand-workflow:no-idle-llm-lane-refill) is burst-only if used; prefer Priority-aware + Lane peer.

## Universal conductor rules
1. One coding lease per checkout.
2. Evidence decides done.
3. Outcome → verify → constraints → boundaries → iteration → blocked stop.
4. Tighten vague goals instead of spam CONTINUE.
5. Ping Jeff only for owner gates (Bob front door).
6. Read real meters — never invent %.
7. Heavy coder vs light conductor.
8. Smoke before trust after outages.
9. Absolute checkout in every Goal.
10. Model chip must match the ask.
11. Work-now visibility: repo/PR/goal; Gemini + MiniMax on the board when active.

## Per-model pins (BYOK / Mini first)
- **Codex**: Mac Goal paste preferred; Cloud `gpt-5.3-codex` only with spend headroom.
- **Claude**: Mac Claude.app paste preferred on FREE leftovers; Cloud `claude-sonnet-4-6` (or newer sonnet Jeff named) only with headroom.
- **Gemini**: **BYOK first** via `GEMINI_API_KEY` (research/critique/large-context). Do not default Cursor Cloud `gemini-*`. Cloud Gemini = last resort only.
- **Grok**: conductor on Bob only; **no Grok worker / Cloud `grok-*` fills** until ~6-day usage reset (Jeff 2026-09-26 ~11:55 AM CT).
- **MiniMax**: BYOK only — default critique `MiniMax-M2.7` (or `M2.7-highspeed` cheap/fast); hard judgment `MiniMax-M3`. `Text-01` obsolete / not in live `/v1/models`. Hosted music-3.0 gated 410 for this key; empty balance 402 blocks chat until Jeff recharges — do not invent success. Never Cloud model; never WebJam coding lane (Codex sole); capped critiques via MiniMax Runner peer (Bob skill fallback).

## Anti-waste + spend wall
Preference: BYOK → Mini paste → LOCAL Cursor Composer (`local_cursor`, **active** lane) → Cloud BA last resort. Under `BLOCKED_SPEND_WALL`: zero new Cloud BA; Mini/local_cursor/BYOK/Actions only. Path tags `mini`|`byok`|`local_cursor`|`cloud`. No double-dip (do not burn Cursor Other Models when direct keys / Mini can do the job). No Grok worker until ~6-day reset.

## Rank 1 hardenings (2026-09-25 ~1:01 AM CT retro)
- Status string exact: Lane + MiniMax = **`SILENT_CAPPED_PEER`** (never `SILENT_CAPPED_LIVE` unless Bob documents exception).
- Mode: Bob sole writer; `go_max` burst allowed **with one WebJam coding sole**; peers never dual-write mode keys.
- Peer→Bob default **`priority:false`**; Jeff only sees Bob front door for real gates.
- Tip SHA move → refresh PR body tip/CI claims same pulse; MiniMax tip **once per SHA** then idle under cap.
- Cadence PRs: no generated `status.json`/`index.html` in the PR; Refresh regenerates them.

## Hard fences
Show Night PARKED. Barker = rupret007/barker. WashOps display name (StoryOps-AI remote rename needs Jeff yes). No merge/undraft/Latest/send without Jeff. hold_final_build until Karen MATCH then Jeff Final Build. No agent deletes / no secret printing in Rank 1 reversible apply.

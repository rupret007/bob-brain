---
name: Multi-LLM stack smoke test
description: >-
  use this when Jeff wants to test Codex, Claude, Grok, Gemini, and MiniMax —
  Level A availability, Level B live ping, Level C control probes with evidence
  and no secret leaks
---
# Multi-LLM stack smoke test

## When
Use when Jeff says “test the models,” “check Claude/Codex/Gemini/…,” after a login/outage, before overnight routing, or when a meter/auth looks wrong. Also run **Level A** as part of Multi-LLM usage pulse when cheap checks are free.

**Do not** burn Ultra/Sonnet/Fable on full Level B overnight by default — Level A first; Level B only on Jeff ask or after a real fail.

Machine for app checks: `Jeffs-Mac-mini.local` (`53abfd07-b321-433b-b068-55620c6c756d`). Evidence folder: `~/Documents/bob-overnight-inject/YYYYMMDD-HHMM-llm-smoke/` (and mirror under `/workspace` when useful).

## Pass / fail rules
- **PASS** only with evidence (screenshot crop, CLI stdout, key-presence bool, HTTP status) — never “looks fine.”
- Write `SMOKE_RESULT.md`: one row per model — Level, status PASS/FAIL/HOLD, evidence path, next action.
- Jeff wake only for login/spend/signing gates; silent HOLD when already known.

## Level A — availability (cheap, preferred default)
| Model | Check | PASS if |
| --- | --- | --- |
| **Codex / ChatGPT** | ChatGPT.app frontmost or Usage UI OCR; `models_cache` / goals sqlite readable if present | App launches; Usage & billing readable OR Goal thread visible; note general % if shown |
| **Claude** | Claude.app open; `claude whoami` / auth path; Billing Pro row | Signed in Jeff; Sonnet selectable; note OAuth vs API-key-only (API-only = HOLD for Pro overnight) |
| **Grok Bot** | This chat responds; Usage & Billing in app if needed; Cursor on-demand vs $10 | Bob can SendToUser; on-demand ≤ ceiling |
| **Grok Cloud** | Cursor Cloud Agents policy + recent launch ability | Included Ultra preferred; on-demand hard cap $10 — do not launch a paid agent just to smoke |
| **Gemini** | BYOK key PRESENT (env/1P/dashboard path Bob already uses); optional `gemini -p "ping"` **only if Jeff asked Level B** | Key present = A-PASS; live ping = B |
| **MiniMax** | BYOK key PRESENT; optional tiny TTS/chat ping on Level B | Key present = A-PASS |

Also: coord leases glance (no claim). Record keys as PRESENT/ABSENT only — never print secrets.

## Level B — live ping (Jeff ask or post-fail)
One **tiny** prompt each, prove a reply, then stop. No Goals, no multi-file edits, no Cloud agents.

| Model | Ping | PASS if |
| --- | --- | --- |
| Codex | New short chat or idle composer: `Reply with exactly: CODEX_SMOKE_OK` then blue-send (not a Goal) | OCR/composer shows that string in reply |
| Claude | Claude Code/app: same `CLAUDE_SMOKE_OK` with Sonnet 5 | Reply contains marker |
| Grok | Already proven by this skill run’s chat reply `GROK_SMOKE_OK` in RESULT | Marker in SMOKE_RESULT |
| Gemini | CLI/API one-shot with marker `GEMINI_SMOKE_OK` | Marker in stdout |
| MiniMax | Smallest chat or TTS “ok” with marker `MINIMAX_SMOKE_OK` | Marker or audio path noted |

Abort Level B if any meter shows exhausted / usage limited — mark HOLD and route around.

## Level C — controls (only when debugging inject/unstick)
| Model | Probe | PASS if |
| --- | --- | --- |
| Codex | Progress-row visible; branching-arrow unpause works OR Steer visible when Working; Set Goal accepts ≤500-char throwaway then `/goal clear` or clear | Screenshot before/after; no Replace-goal pollution |
| Claude | Plan mode toggle; `/clear` works; optional throwaway `/goal` then clear | UI/CLI confirms |
| Grok | Stall-watch recipe + SendToUser | Already covered by routines |
| Gemini | `/memory show` or GEMINI.md load | Context lists expected file |
| MiniMax | Skip unless voice path broken | — |

Never leave a throwaway Goal active on WebJam production thread — use a scratch chat or clear immediately.

## Output template (`SMOKE_RESULT.md`)
```
# LLM smoke YYYY-MM-DD HH:MM CT
Level: A|B|C
Codex: PASS|FAIL|HOLD — evidence …
Claude: …
Grok Bot: …
Grok Cloud: …
Gemini: …
MiniMax: …
Meters: chatgpt% … claude … grok … on-demand $
Jeff gate: none | login | …
```

## Pair with
- [Multi-LLM stack mastery](sand-workflow:multi-llm-stack-mastery)
- [Best LLM for the job](sand-workflow:best-llm-for-the-job)
- Usage pulse routine (Level A overlap OK; don’t duplicate Jeff pings)

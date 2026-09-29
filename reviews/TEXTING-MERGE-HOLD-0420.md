# Texting — MERGE HOLD — 0420 CT

**When:** 2026-09-28 04:23 CDT
**Isolated tip:** `97513468016488ebe42ca1919e507db99fc0a15f` (`9751346`) on `draft/webbob-texting-0927`
**Live prod:** `a777736` (integrate shipped; rollback `rollbacks/webbob-integrate-20260928-040432`)
**Draft PR #8:** OPEN draft, head matches `9751346`, base `draft/webbob-clean-0927`

## Gate check
| Check | Result |
| --- | --- |
| Offline READY (TEXTING-READY-2014) | YES — 295 webchat / 121 services |
| LIVE Gemini+MiniMax on isolated tip | BOTH_PASS (`TEXTING-REREVIEW-2143.md`) |
| Merge into `draft/webbob-clean-0927` (lineage has integrate `a777736`) | **CONFLICT** |
| Deploy | **BLOCKED** — would regress integrate if tip deployed alone |

## Conflicts (dry-run merge 9751346 → clean @ f7c2797)
1. `webchat/app.py` — content conflict: texting tip adds `Texting` hooks / changes `submit`/`public`/`status_reply` paths; integrate tip keeps worker_assignment, status_observation, reply_authority wiring.
2. `reviews/WEBBOB-EVALS-0927.md` — add/add conflict.

Ancestry: merge-base(texting, integrate) = `dff84e3`. Neither tip is ancestor of the other.

## Decision
**Do NOT merge/deploy isolated `9751346` onto live `a777736`.** Relaunch Codex fix lane to merge texting onto integrate base in worktree `workspaces/webbob-texting-onto-a777736-0420` on branch `draft/webbob-texting-onto-a777736`, preserve BOTH texting consent/delivery_unconfirmed AND integrate worker/status features, re-run full suites, regular-push, file TEXTING-FIXED-0420 / TEXTING-READY-0420 (or STILL-FAIL). Fresh Gemini+MiniMax LIVE review required on the new combined SHA before any deploy.

No Jeff notify. No force-push. No Grok heavy coding.

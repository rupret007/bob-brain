# Texting deploy gate — FAIL — 2026-09-27 ~18:41 CDT

**Candidate tip:** `draft/webbob-texting-0927` @ `8f82fc0`  
**Worktree:** `workspaces/wt-webbob-texting-0927`  
**Live tip (unchanged):** `dff84e3`  
**Deploy this run:** NO

## Cross-vendor reviews

| Review file | Verdict |
| --- | --- |
| `LIVE-GEMINI-draft_webbob-texting-0927-8f82fc0.md` | **FAIL** — E2E proof script asserts mock "Sent via Andrea" while committed evidence/screenshots show blocked "Not sent" path |
| `LIVE-MINIMAX-brain_draft_webbob-texting-0927-8f82fc0.md` | **FAIL** — claims criticals: `public()` exclusion order, timing-safe compare test gaps, missing "Sent via Andrea" message test, duplicate save |
| `LIVE-GEMINI-brain_draft_webbob-texting-0927-a72f8a6.md` | PASS on older SHA `a72f8a6` only — does **not** clear tip `8f82fc0` |

## Gate checklist

- [ ] Full webchat+services tests green on tip (needs re-run after fix)
- [ ] Eval suite evidence (`WEBBOB-EVALS-0927.md`) — **missing; do not invent**
- [x] Cross-vendor PASS on same tip — **FAIL** (Gemini + MiniMax FAIL on 8f82fc0)
- [ ] Rebased/stacked cleanly onto live `dff84e3` for one-lane deploy

## Required before deploy

1. Harmonize browser proof + evidence (mock-send artifacts OR script asserts blocked path honestly).
2. Address/refute MiniMax criticals with code+tests (`hmac.compare_digest` already present — verify + add success-message test; fix `public()` exclusion order; drop duplicate save if still present).
3. Fresh LIVE Gemini + LIVE MiniMax PASS on the **same** new tip SHA.
4. Full unittest suites + optional Playwright proof.
5. Then deploy ONE lane onto `dff84e3` with rollback + webchat/job-runner-only restart.

## Action this loop

Relaunch coding lanes on existing texting worktree; no live deploy.

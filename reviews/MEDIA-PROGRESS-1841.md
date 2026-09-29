# Media lane progress — LOOP tick 1841 (2026-09-27)

**Worktree:** `workspaces/wt-webbob-media-0927`  
**Branch:** `draft/webbob-media-0927` (draft only; no deploy/merge/undraft)  
**Tip SHA (local):** `a46d68c` — Address MiniMax media review gaps without weakening Gemini-pass security.  
**Prior Gemini PASS baseline:** `95f71b4` (`LIVE-GEMINI-draft_webbob-media-0927-95f71b4.md`)  
**MiniMax FAIL addressed from:** `LIVE-MINIMAX-brain_draft_webbob-media-0927-7c6a6cb.md`

## Conductor review disposition

| Review | Verdict | Action this tick |
| --- | --- | --- |
| LIVE-GEMINI @ `95f71b4` | **PASS** | Preserved: conversation-bound media, OCR secret gate, bounded `MediaBudget`, Gemini header auth, Range video serve |
| LIVE-MINIMAX @ `7c6a6cb` | **FAIL** | Implemented required code/test fixes on draft tip (see below) |

### Fixes applied (MiniMax required list)

1. **`read_text_file`** — Already complete on draft (`95f71b4`); non-PDF return path verified + regression test added.
2. **`_check_signature`** — `len(data) >= 8` for ISO-BMFF; `len(data) >= 12` for WebP.
3. **`prompt_image_bytes`** — Progressive quality/scale fallback before hard failure.
4. **`split_transport`** — `base64.b64decode(..., validate=True)` on each vision part.
5. **Browser upload signatures** — Already enforced via `store_media` → `_check_signature`; added octet-stream regression for truncated fake MP4.
6. **Multi-attachment budget** — Already enforced via shared `MediaBudget` deadline in `enrich_for_model` (unchanged).
7. **Video frames** — Continue sampling on per-frame failure instead of stopping at first error.
8. **Tests** — Signature, transport base64, progressive image fallback, non-PDF read, HTTP octet-stream rejection.

**Out of lane (unchanged):** voice barge-in parity — not in media scope; still noted in MiniMax Bob parity table.

## Verification (this tick)

```text
cd webchat && python3 -m pytest -q --tb=short
cd services && python3 -m pytest -q --tb=short
```

| Suite | Result |
| --- | --- |
| `webchat` pytest | **284 passed** |
| `services` pytest | **120 passed** |

Browser/media gate (`reviews/run-webbob-tests.sh`) not re-run this tick; pytest-only scope per loop instruction.

## Push status

```text
git push brain draft/webbob-media-0927
```

**Rejected (non-fast-forward).** Local branch is ahead of remote with rebased history (`ahead 14, behind 2` on `brain/draft/webbob-media-0927`). No force-push performed (loop constraint).

## Verdict

**STILL-FAIL** for deploy-ready in the conductor loop until:

1. Draft remote accepts `a46d68c` (maintainer-chosen integration or `--force-with-lease` on this draft branch only), and  
2. A fresh **LIVE-MINIMAX** review on the new tip passes.

**Local readiness:** code and tests satisfy the recorded MiniMax FAIL remediation list without regressing Gemini PASS security claims at `95f71b4`.

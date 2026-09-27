---
name: Board work-now publish freshness
description: >-
  use this when refreshing or publishing bob-ops-dashboard — llm-work-now.json
  must rewrite generated_at every rebuild so Pages never freezes behind
  status.json; PASS bar = matching stamps after publish (in-process write alone
  ≠ PASS)
---
# Board work-now publish freshness

Locked 2026-09-25 ~07:18 CT after Jeff-visible hole: Pages `llm-work-now.json` stuck at **02:37 CT** while harden R125 closed **06:06 CT** (~4.5h SoT lag).

**K4 bump 2026-09-25 ~08:05 CT:** bar = matching stamps after publish; in-process write alone ≠ PASS.

**Retro 2026-09-25 ~1:09 PM CT:** K2/K3 proved closed (live Pages status + llm-work-now both **13:08 CT**). Actions YAML safety added after #61.

**Retro 2026-09-25 ~10:09 PM CT:** Dual-SoT **held** (live Pages both **22:02 CT**). New honesty hole: AI Music Vault chip still `private: true` while GitHub `visibility: public`.

## Rule
Every `./refresh.sh` (local or Actions) must:
1. Finalize llm_work via `finalize_llm_work_after_live_poll` (stamp → validate → demote).
2. Call `board_meta.write_llm_work_now_json(root/"llm-work-now.json", llm_work, generated_at_ct=CT_stamp)`.
3. **K3:** Set `status.llm_work_now_freshness` via `build_llm_work_now_freshness_meta` from the **same** llm-work-now blob that will be committed — never claim `ok` on a stale paired artifact.
4. Commit/push `llm-work-now.json` with status/index (`PAGES_ARTIFACTS`) — never `cp` a stale blob as the only publish.
5. **K2:** Before declaring PASS (and post-push), `assert_dual_sot_files(status.json, llm-work-now.json)` — FAIL if stamps diverge >60s or `freshness.ok` while blob age > TTL (1200s). Prefer working-tree / about-to-commit files, not remote Pages.
6. **Repo visibility honesty:** each project’s `private` (and notes that say Private/Public) must match live GitHub `visibility` / `private` for that repo. Hard-coded “Private catalog…” text is FAIL when the repo is public (Vault 2026-09-25). Refresh must re-read visibility each run, not cache a fence Jeff already lifted.

## PASS bar (K4)
- **PASS** only when `status.llm_work_now_freshness.generated_at` matches `llm-work-now.json` `generated_at` (exact or ≤60s skew) on the published / about-to-commit pair.
- In-process rewrite of llm-work-now **alone** is not PASS — dual-SoT assert must clear.
- Live Pages match within ~5m of refresh is the Jeff-visible confirmation; Actions dual-SoT assert is the fail-closed gate.
- Dual-SoT PASS does **not** excuse a wrong `private` chip or stale release chip.

## Actions YAML embeds (2026-09-25 ~08:05 CT)
PR #60 put an unindented `python3 <<'DUALSOT'` heredoc inside `run: |`; the de-indented body terminated the YAML block → invalid workflow (`workflow_dispatch` 422, 0s push failures). Hotfix #61 used `python3 -c` one-liners.

**Rule:** inside Actions `run: |` blocks, prefer `python3 -c '…'` one-liners or a checked-in script path. Never an unindented heredoc that can end the block. After editing refresh workflow YAML, dry-run with `workflow_dispatch` or confirm the file still parses before claiming green.

## Symbols
- `board_meta.build_llm_work_now_payload`
- `board_meta.write_llm_work_now_json`
- `board_meta.build_llm_work_now_freshness_meta` (K3)
- `board_meta.dual_sot_assert_errors` / `assert_dual_sot_files` (K2)
- `board_meta.DUAL_SOT_MAX_STAMP_SKEW_SEC` (=60)
- `refresh.sh` after finalize (R126 wire) + post-write / post-push assert
- `.github/workflows/refresh-dashboard.yml` Dual-SoT step + post-push re-assert

## Fail-closed checks
- Live Pages `generated_at` must be within ~20m of last refresh (or last push).
- Soft-paint uses `status.json` `llm_work`; Pages artifact must still match honesty + stamp.
- Idle-class sources never publish `status=running` (validate on write).
- Dual-SoT assert FAIL aborts the refresh job — do not soft-pass on stamp drift.
- Visibility mismatch (board `private` ≠ GitHub) is an honesty FAIL even when stamps match.

## Pair with
- [Conductor self-improvement loop](sand-workflow:conductor-self-improvement-loop)
- [Multi-agent lease board sync](sand-workflow:multi-agent-lease-board-sync)
- [Finish-out watchdog](sand-workflow:finish-out-watchdog)

## Stale WARN (R126 keep-going)
- `board_meta.llm_work_now_freshness_warnings` / `LLM_WORK_NOW_STALE_WARN_SEC=1200`
- Refresh writes `status.llm_work_now_freshness` via `build_llm_work_now_freshness_meta` and prints `WARN …` if stamp age > TTL
- Jeff-visible: Actions log + status meta; chips unchanged by WARN alone

## Race residual → keepers (2026-09-25)
Measured: Actions run **36137598706** — unstaged `llm-work-now.json` blocked rebase. Live Pages later showed status **07:54** vs llm-work-now **07:24** while `status.llm_work_now_freshness.ok=true` (false-negative).

- **K1 (merged #59):** `PAGES_ARTIFACTS` + stash→rebase.
- **K2/K3 (merged #60 + YAML hotfix #61):** post-push / pre-PASS dual-SoT assert + freshness from paired blob; Actions embeds via `python3 -c`.
- **Proved:** smoke run **36138744301** success; live Pages matching through evening (**22:02 CT** / **22:02 CT**).
- **K5 (stub):** `repository_dispatch` types `refresh` / `release-published` — wire webjam `release.published` as follow-up; until then, manually dispatch refresh after Latest publish.
- **K7 (open, still FAIL 2026-09-26 13:03 CT):** live Pages still shows AI Music Vault `private: true` / “Private catalog…” while GitHub `visibility: public`. Re-read GitHub visibility each refresh; ship the board fix on next bob-ops press (DRAFT only; Jeff undraft). Dual-SoT stamps alone ≠ honesty PASS.

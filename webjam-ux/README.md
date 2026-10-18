# WebJam novice UX review — 2026-09-26

Authorized by Jeff: many code-grounded MiniMax-M2.7 passes, Gemini and Claude critique,
one Codex implementation lane, small commits and a draft PR. No merge, undraft,
force-push, messages, or changes to `~/Andrea_NanoBot`.

## Discovery

- Main checkout: `/Users/jeffstory/Documents/webjam`.
- Sole existing active worktree: `/Users/jeffstory/Documents/webjam-pr158-fold`.
- Draft #158: `codex/start-ux-copy-polish`, `b11a7c44f79a672328110f0054a86d6106c6e0b4`.
- Draft #159: `codex/host-startup-checklist`, `885a324d46ef3353507e6b38ecf220c3bcddf19f`.
- Draft #160: `codex/rehearsal-recap-card`, `6b8d069a5f4e5999c98e23aaffca2f64c11f5c46`.
- #160 contains the #159 checklist plus recap. Its tracked dirty edit changes a
  test assertion from `_choice_helper` to `_host_reason`. Untracked closeout files
  are outside the change and must not be committed.
- The queued identity coder failed at Cursor authentication before editing.
- This session cannot write the original worktree or Git metadata. `repo/` is an
  isolated writable clone; it preserves the original worktree and allows normal
  fast-forward pushes to existing draft branches. It is the only new coding lane.

## Accounting

Rates verified against MiniMax's published pricing on 2026-09-26:
[MiniMax pricing](https://platform.minimax.io/subscribe/token-plan?tab=api-enterprise).
M2.7 standard input $0.30/M tokens; output $1.20/M tokens. No cache discount assumed.
`spend.log` is append-only JSONL with actual response token usage. Before every call
a locked ledger reserves worst-case input at $0.375/M (cache-write rate), byte count
as a conservative token bound, plus capped output. Uncertain calls retain their
reservation; no silent retry. Admission stops before committed/reserved spend would
exceed $48, leaving a margin under the authorized $50 credit. This estimates this
review's spend, not the account's balance or other services' usage.

The existing `bin/ask-minimax.sh` delegates `--ux-pass` to `paid_review.py`; its
ordinary question interface remains unchanged. Full source prompts, raw responses,
final reviews, and accounting are retained here. Empty/truncated final answers do
not count as completed reviews.

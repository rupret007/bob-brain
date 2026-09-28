# Texting lane fixes — 2026-09-27

> Historical checkpoint. Current fixes and validation are in
> `TEXTING-FIXED-1841.md`. The current adapter probes Andrea’s bridge after durable
> consent; the browser proof records its rejection and zero deliveries. The
> no-send-endpoint statement below describes this earlier implementation only.

**Branch:** `draft/webbob-texting-0927` (draft PR #8, base `draft/webbob-clean-0927`)
**Worktree:** `workspaces/wt-webbob-texting-0927`
**Scope:** Address valid review findings without changing delivery policy (Andrea/BlueBubbles send remains blocked; separate `yes wbtxt-…` only).

## Review inputs

| Source | Action |
| --- | --- |
| `reviews/CURSOR-REVIEW-TEXTING-0927.md` | Fixed medium finding #1 (help routing); noted other items as by-design or follow-up |
| `reviews/MINIMAX-REVIEW-TEXTING-0927.md` | Fixed `read_only` regression (#7); declined false positives (single-owner install, session digest server-bound, thread ACL, in-memory BB password API contract) |
| `reviews/WEBBOB-TEXTING-0927.md` | Unchanged delivery stance — confirm records consent, returns **Not sent.** |

## Changes made

1. **Colloquial chat no longer hijacked by texting help** (`webchat/texting.py`)
   Removed the `^text \S` arm from `help_request`. Incomplete commands such as `send a text to` still show texting help; phrases like `text me about the bridge mix` fall through to normal Web Bob chat (parity with Grok Bot conversational use of “text”).

2. **Passive live_ops reads restored** (`webchat/ops_panel.py`, `webchat/live_status_snapshot.py`)
   Reintroduced `read_only` on `load_live_ops()` so status snapshot builds do not call `runtime.snapshot()` (state-ledger side effect). `build_live_status_snapshot()` uses `read_only=True` again.

## Tests added/updated

| Test | Purpose |
| --- | --- |
| `test_colloquial_text_phrasing_is_not_texting_help` | Regression for CURSOR finding #1 |
| `test_load_live_ops_read_only_skips_inline_snapshot` | Regression for MINIMAX finding #7 |

## Verification

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **215 passed** |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed** |

No deploy, restart, merge, undraft, force-push, or outbound text. Draft-first and separate-yes consent behavior unchanged.

## Remaining risks (accepted)

- BlueBubbles read API still passes the server password as a query parameter (API contract); errors remain scrubbed in user-visible paths.
- Delivery still requires a future Andrea owner-surface contract; Web Bob does not call send/execute endpoints.

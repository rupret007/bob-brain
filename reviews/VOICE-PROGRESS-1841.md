# Voice Progress — 1841

Workspace: `~/Documents/bob-overnight-inject/workspaces/wt-webbob-voice-0927`
Branch: `draft/webbob-voice-0927`
Tip SHA (unchanged): `cd5e8e2`

## Summary

Investigated both LIVE MiniMax FAIL reports against the actual tree at `cd5e8e2`.
Every blocking finding in both reports turned out to be a **diff-review artifact**
(the reviewer only saw a truncated/partial diff, not the full files) rather than a
real defect in this codebase. No source changes were required. Full test suite
verified green.

## LIVE-MINIMAX-draft_webbob-voice-0927-cd5e8e2.md — claims checked

| Claim | Verdict | Evidence |
|---|---|---|
| `voice.js` truncated mid-word | **False positive** | `webchat/static/voice.js` is 291 lines, ends with a complete class body and `window.BobVoice = BobVoice;`. `node -c webchat/static/voice.js` passes. The reviewer was looking at a diff hunk cut off at line 291, not the actual EOF. |
| SEC-1 CSRF "not visible in diff" | **False positive** | CSRF is enforced centrally in `RequestHandler.dispatch()` (`webchat/app.py:1143-1146`) for every `POST /api/*` route, including `/api/voice/*`, before any voice-specific handler runs. `test_voice_csrf_required_on_all_routes` and `test_voice_auth_csrf_origin_and_tailnet` already exist in `webchat/test_voice.py` and pass. |
| Missing `entries` type validation on `/api/voice/transcript` | **False positive** | `voice.py:159` already does `if not isinstance(entries, list) or len(entries) > 40: raise VoiceError(400, ...)`, covered by `test_invalid_transcripts_are_atomic`. |
| `reply()` StopIteration risk | Real but intentional/handled | Confirmed via test run — `test_sweep_stuck_falls_back_to_last_message_without_reply_id` deliberately drives this path; `sweep_stuck()` recovers the stuck message to `status: error`. No behavior change needed. |
| `voice.logout()` outside `chat.lock` | Reviewed, no fix needed | `chat.voice.logout()` operates on the voice module's own internal lock/state (call ownership), not `chat.sessions`; popping the session afterward under `chat.lock` is the correct scope — they protect different data. |
| CSP wss target should be locked to Gemini domain | Already the case | `connect-src 'self' wss://generativelanguage.googleapis.com` is already scoped to the exact host, not a wildcard. |

## LIVE-MINIMAX-brain_draft_webbob-voice-0927-8e2996c.md — claims checked

| Claim | Verdict | Evidence |
|---|---|---|
| ReDoS in `job_queue.py` START regex | **False positive** | `[:,\s]+` is a flat character class with a single `+`, not nested/ambiguous quantifiers — matching is linear. Benchmarked a 5,000-char adversarial separator: match completed in ~67µs. No catastrophic backtracking is possible with this pattern shape. |
| Race condition: snapshot taken before `self.workers[identifier]` populated | **False positive** | `launch()` carries the comment "Caller holds self.lock; the same saved assistant message is reused" (`webchat/app.py:610`) — the snapshot, dict write, and `worker.start()` all happen while the caller already holds `self.lock`. The spawned thread's first action in `complete()` also acquires `self.lock`, so it blocks until `launch()`'s caller releases it. No reordering needed. |
| Missing Python voice test coverage (9 named tests) | **False positive** | All nine listed scenarios already exist under different names in `webchat/test_voice.py`: concurrent voice/text (`test_concurrent_voice_and_text_rejected`), reply pinning (`test_tool_context_is_pinned_before_worker_thread_starts`), call limits (`test_owned_call_and_duplicate_start`, `test_voice_start_rate_limit`), transcript atomicity/no-rollback (`test_stale_transcript_write_cannot_roll_back_newer_words`, `test_invalid_transcripts_are_atomic`), lease recovery (`test_expired_tab_lease_releases_slot_but_allows_final_transcript`), CSRF (`test_voice_csrf_required_on_all_routes`), job regex (`test_spoken_job_punctuation_uses_same_dispatcher_without_rewriting`). |
| Missing CSRF test for voice API | **False positive** | See above — both CSRF tests present and passing. |

## Test run (this session, `cd5e8e2`)

- `python3 -m unittest test_voice -v` (webchat): **24/24 pass**, including both CSRF tests.
- `python3 -m unittest discover -p "test_*.py"` (webchat): **273/273 pass**.
- `python3 -m unittest discover -p "test_*.py"` (services): **118/118 pass**.
- `node test_voice_js.cjs` (webchat): **18/18 pass**, including the Safari-suspended-playback test the report claimed was missing/misnamed.
- `node -c webchat/static/voice.js`: syntax OK.

No source files were modified — the tree already satisfies both review requests.

## Push status

`draft/webbob-voice-0927` (local, `cd5e8e2`) has diverged from `brain/draft/webbob-voice-0927`
(tip `8e2996c`): 5 commits ahead / 2 commits behind, with a shared ancestor far back at `7ab7f13`.
The 2 brain-only commits (`cf46be9`, `8e2996c`) rewrite large parts of `webchat/`, `services/`,
and `state/` from a different pass (including deleting files like `deploy_parity.py`,
`draft_publish.py`, `pr_evidence.py`, `build_info.py`, `live_redeploy_check.py` that exist on
this branch) — this looks like a different worker's lane state, not a simple rebase.

Attempted a plain `git push brain HEAD:draft/webbob-voice-0927`: rejected as non-fast-forward
(expected, no force-push attempted). Reconciling the two histories requires a merge/rebase
decision that is out of scope for this session's guardrails ("Drafts only. No deploy/merge/
undraft/force-push."). Left both branches untouched pending a coordinator decision.

## Verdict

**READY** (code and tests) at tip SHA `cd5e8e2`. voice.js is complete, CSRF tests for all voice
routes exist and pass, and the full test suite (273 webchat + 118 services + 18 JS + 24 voice)
is green. The only open item is the branch divergence with `brain/draft/webbob-voice-0927`,
which needs an explicit merge/rebase decision from a coordinator before the draft can be pushed
there — flagging as **STILL-FAIL (push only)** so a later loop with merge authority can resolve it.

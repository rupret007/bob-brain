# Web Bob READY-FOR-PHONE (TOP PRIORITY, Jeff 00:24) — Cursor lane, coordinate with Codex svc-webchat-failover (read conductor/WEBCHAT-FAILOVER.md incl URGENT UPDATE; don't fight its edits: git diff first, small patches)
Jeff is using https://jeffs-mac-mini.tail758ab4.ts.net on his iPhone now. Must reliably answer every message.
Observed bugs:
1. "No provider completed a reply. codex/cursor/gemini: busy with another job" — Bob already changed providers.py lane() lock name to chat-<provider>. Verify all providers (incl Gemini helper's own lease, MiniMax) never block on background job locks. MiniMax must be in the chain as last resort.
2. 409 "Bob is finishing another reply" is GLOBAL — one stuck reply blocks every conversation. Make it per-conversation, and auto-expire a stuck reply after its timeout; the UI must show a Stop button and a clear retry.
3. Replies sat "queued" with provider null. Ensure the worker picks up immediately.
4. Fast path: short/simple messages go to the fastest healthy provider (Gemini API is fast) with a total budget ~60s; long tasks may use Codex/Cursor. Show "thinking via X" progress.
5. Mobile: input stays usable, auto-scroll, Enter/Send works on iOS Safari, add-to-home-screen works.
Test: unit tests + live curl through the ts.net URL (Origin header, lowercase UUID request_id, password from conductor/webchat/.password never printed): 10 back-to-back messages in 2 conversations while background jobs hold lane locks => 10 replies, none "busy", p50 latency noted. Plus "merge #158" refused.
Then: python3 conductor/services/council.py critique (Gemini+MiniMax, Claude short) of the diff, apply valid points. Restart server (kill 127.0.0.1:8787 PID, bash conductor/webchat/start.sh), keep .public-origin.
Commit to draft branch. Write conductor/reviews/WEBCHAT-READY-RESULT.md with PASS/FAIL table, latency, SHA.

## Self-assessment (Jeff 00:24) — required
After each change set: honestly score Web Bob 1-10 on reliability, speed, mobile UX, failover, safety, with evidence (measured latencies, failures seen). List the weakest area, fix it, re-test, re-score. Loop until all >=8 or 3 rounds. Include the scorecards in WEBCHAT-READY-RESULT.md. No inflated scores; fail-closed if not measured.

## North star (Jeff 00:24): "It needs to work just like Bob, as close as possible."
Match Grok Bot Bob behavior: warm, concise replies in full sentences; answers first; loads bob-brain profile/memory/skills/BOB-OPERATING-RULES every message; knows current jobs/PRs/status; can start mini screen jobs (Codex/Cursor) for real work and report back; confirm cards for risky actions (merge/undraft/send/spend); never sends texts/emails without yes; short progress updates while working; remembers the conversation. Add a "Bob parity" row to the self-assessment scorecard (test with 5 typical Jeff asks: status, "anything I need to do?", start a job, a memory question, a refusal) and compare tone/usefulness to Bob's style.

## Clean failover BOTH WAYS (Jeff 00:26) — required
Shared ledger: conductor/handback/ (local on mini).
A) Bob -> Web Bob: Bob keeps conductor/handback/BOB-STATE.md (what's running, open asks, pending confirmations, priorities). Web Bob reads it on every message so it picks up exactly where Bob left off.
B) Web Bob -> Bob: every Web Bob turn appends to conductor/handback/HANDBACK-LOG.md (timestamp CT, Jeff's ask, provider, jobs started w/ screen+spec, files changed, commits/SHAs/PRs, confirmations Jeff gave, refusals, open items). Maintain HANDBACK-SUMMARY.md = digest since mtime of conductor/handback/.bob-last-seen, grouped done / running / waiting on Jeff / risks.
C) UI: "Handback" chip showing summary + BOB-STATE.
D) No double work: before starting a job, both sides check screen -ls + ledger for the same task.
Test: simulate Bob down -> 3 Web Bob turns -> verify log+summary accurate; simulate Bob state -> Web Bob answers "what's running?" from it. Add "Handoff both ways" row to scorecard.

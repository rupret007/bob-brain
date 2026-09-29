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

## ADDED 00:29 (Jeff): Architectural review in the self-assessment
Add an "Architecture" score (0-10) to the scorecard, and it must reach at least 8 like the others. Include a short review in the RESULT file covering:
- Component map: webchat server, providers, locks, job lanes, handback, dashboard-updater, watchdog, Tailscale serve.
- Single points of failure and shared state (global locks, lock files, screen-name collisions, one mini).
- Coupling between chat and the job lanes, and whether chat can starve jobs or jobs can starve chat.
- Failure and recovery paths, stale-lock expiry, and restart safety.
- Security boundary: the password, the public ts.net origin, secrets in the repo or logs.
- The top 5 ranked structural fixes. Implement the ones that are safe tonight, and list the rest with an effort estimate.
Keep everything draft-only, with no merges.

## ADDED 00:30 (Jeff said "Start"): Enhancements, after the reliability fixes pass
1. Mobile formatting: clean markdown, code spans, links, readable lists, a sticky input bar, and no zoom-on-focus.
2. Run jobs from chat: "start a job" queues a screen job on the mini through the existing job runner. It confirms before anything consequential and stays draft-only.
3. Status panel: live lanes, running jobs, recent RESULT files, dashboard freshness, and the handback chip.
4. Voice: a mic button (Web Speech API) for input, and optional read-aloud of replies.
5. Bob parity: use Bob's persona, rules, and memory (from BOB-STATE.md and the handback files) so replies read like Bob's. Short, casual, links and SHAs first.
Score each enhancement in the self-assessment. Commit to the draft branch only.

## ADDED 00:31 (Jeff): Use every resource except Grok
Use every worker except Grok. Codex and the Cursor CLI build, one coder at a time on Web Bob. Run parallel reviews and research with Gemini, MiniMax (stay under the $48 cap), Claude (short critiques only), and the council tool. Keep going until Web Bob matches Bob as closely as possible.

## ADDED 00:32 (Jeff): Push every lane to the max, Cursor first
The MiniMax cap is now $59 (the total balance). Run every lane except Grok at full speed.
- Cursor CLI is the lead builder and gets first pick of the work.
- Codex builds when the Cursor CLI is between rounds. Only one coder touches Web Bob at a time.
- MiniMax (M2.7) and Gemini run continuously in parallel: critiques on every commit, Bob-parity comparisons, research on the lowest scores, test prompts, and architecture review.
- Claude does short critiques.

## ADDED 00:35 (Jeff): Seamless takeover and handback, highest priority for round 2 and later
Bob has about 20% usage left and must stretch it over 5 days, so Web Bob is the primary way Jeff reaches Bob until about 10/2.
- Takeover: Web Bob loads Bob's full working context automatically: BOB-STATE.md, the handback files, standing rules, open PRs, running jobs, and pending personal items. It acts as Bob does (starts mini jobs, reports SHAs, stays draft-only, and needs a separate yes before any text or email).
- Handback: every Web Bob decision, job, and result is appended to HANDBACK-LOG.md and HANDBACK-SUMMARY.md (short and ranked) so that Bob can pick up with one read and zero questions.
- Test both directions: simulate Bob going offline, run 5 real tasks through Web Bob, then check that the summary gives Bob everything he needs. Score "handoff" at 9 or higher.

## ADDED 00:37 (Jeff): The models help each other
Cross-check everything. After each build step, the builder (Cursor or Codex) sends its diff to Gemini and MiniMax for critique and applies their fixes. Gemini and MiniMax review each other's suggestions, and a council vote breaks ties. When one model is stuck or fails, hand the task to another with full context. Log who helped with what in the RESULT file.

## ADDED 00:42 (Jeff): Web Bob gets Bob's self-improvement loop
Give Web Bob the same self-improvement loop Bob has. On a schedule (launchd on the mini, with no Grok):
- Review its own recent chats and failures.
- Score itself, then research fixes with Gemini and MiniMax.
- Have Cursor or Codex implement fixes on a draft branch, run tests, and write a RESULT file.
- Log every round to the handback files.
It stays draft-only, never merges, and never uses Grok. Give self-improvement its own score, which must be 9 or higher.

## ADDED 00:44 (Jeff): Music creation is a core Web Bob use case
Web Bob must be a full AI songwriting partner, covering as much as exists today:
- Lyrics: drafting, rewrites, rhyme and meter help, song structure, and hooks.
- Chords and progressions, melody ideas, arrangement notes, and references.
- MiniMax music model: generate demos and sketches from lyrics plus a style prompt. Stay within the MiniMax $59 cap and log the cost of each call.
- Moises (Jeff has it): stem separation, chord detection, and key and BPM detection for uploaded audio. Research its API or CLI access. If the only option is the app, document the manual handoff clearly.
- Logic Pro MCP on the mini (3.17.0): open projects, markers, tempo, and bounce. Always read-only or confirm first.
- Audio upload and playback in the chat, plus a song-project notebook (lyrics, versions, notes) that persists and hands back to Bob.
- Research the current AI music tools (Suno, Udio, ElevenLabs music, Stable Audio, and others). Rank what's worth wiring in, but only for keys Jeff already has. Never spend money or sign up without a yes from Jeff.
Give "music" its own score, which must reach 9 or higher. Do real tests: write a short song end to end and produce a MiniMax demo.

## ADDED 02:00 (Jeff)
MiniMax music API is not entitled (410). Do NOT chase new endpoints or signups. Use what we have: lyrics/chords/arrangement via LLMs, MiniMax text + speech/TTS if entitled, Logic Pro MCP (read/confirm-first), audio upload/playback, song notebook. Score music on those.

## ADDED 02:03 (Jeff) — Detailed live dashboard
Jeff cannot see terminal work. Make the ops dashboard (agents-status.json + Pages) show, per running screen/job: what it is doing now (last 3 log lines, plain English), round number, started time, elapsed, last commit SHA+message, current scores table, which model is building/reviewing, MiniMax spend vs $59 cap, and stalled/finished state. Mobile-friendly. Data-only pushes, no secrets in logs. Also show it inside Web Bob as a status panel.

## ADDED 02:07 (Jeff) — TOP PRIORITY: conductor inside Web Bob
Everything Bob does as conductor must also work from inside Web Bob before Bob usage runs out: see and control the autopilot/rounds, start/stop screens, launch Cursor/Codex jobs, call the council (Gemini/MiniMax/Claude), read scores/SHAs/logs, watch the live dashboard, handback to Bob. Same safety rules (drafts only, confirm-first for merges/sends/spend, never Grok). Score "Conductor parity" as its own row and prove it with a drill: Jeff runs one full round only from Web Bob on his phone.

## ADDED 02:08 (Jeff) — Research-first design
Every round starts with a short research pass on what exists today (for example open-source agent orchestrators, multi-agent frameworks, assistant failover/handoff patterns, mobile AI chat UX, AI music tools), then writes a DESIGN note: what we borrow, what we reject, and why. Use Gemini (search-grounded) plus the council to rank ideas. Aim for the most logical, well-designed system, not just passing scores. Cite sources in the result file.

## ADDED 02:11 (Jeff) — iPhone-first redesign, make it look AMAZING (TOP of queue)
Jeff: current phone UI is horribly designed; iPhone is the primary device. Seen: raw status dump (markdown headers, file names) fills the screen above chat; STATUS.md/Latest review/Jobs detail/Model lanes/Song project/Reply-with crowd out the conversation; jargon footer. Redesign to feel as polished as iMessage/ChatGPT/Claude iOS: chat fills the screen; slim header (name + status dot); status/jobs/songs/lanes/settings in a bottom sheet or tab bar; plain English, no file names or raw markdown; beautiful typography, spacing, subtle motion, dark/light; 44pt tap targets; safe-area insets; composer pinned above keyboard. Research best mobile AI chat UX first. Playwright screenshots at 390x844 and 430x932 in result; council reviews screenshots; score iPhone design separately, must be >=9.

## ADDED 02:18 (Jeff) — Layout decision
Chat takes most of the screen (at least ~75% of height) and must be big enough to be truly useful. Bottom tab bar (iOS style) with separate tabs: Chat (default), Jobs, Models/LLM status, Songs, Settings. No status panels above the chat.

## ADDED 02:18 (Jeff) — Layout decision
Chat takes most of the screen (at least 75 percent of height) and must be big enough to be truly useful. iOS-style bottom tab bar with separate tabs: Chat (default), Jobs, Models (LLM status), Songs, Settings. No status panels above the chat. Base design = the Grok Bot iPhone app (this very assistant app Jeff uses): chat-first full-height conversation, clean message bubbles, slim header, composer pinned at bottom, extras tucked away. Match that feel and make it better and more useful.

## ADDED 02:19 (Bob, Jeff approved) — Useful extras
- Push notifications (web push on iOS home-screen app) when a job finishes, fails, or needs a yes.
- Approve/deny cards in chat for anything confirm-first (merge, send, spend), one tap.
- Quick-action chips above composer: Status, Start round, Ask council, New song.
- Streaming replies with typing indicator; tap-to-copy code; long-press message menu.
- Conversation list with search; pin important chats.
- Attach photos/screenshots and audio from the phone.
- Offline/reconnect banner and message retry; never lose a typed draft.
- Which model answered, shown subtly per message.
- Face ID-style quick unlock (WebAuthn passkey) instead of retyping password.
- Morning digest card: what ran overnight, scores, what needs Jeff.

## ADDED 02:22 (Jeff) — Intelligence and logic
Raise how smart Web Bob is, not just UI: route each request to the best model for the job (reasoning vs fast vs code vs music); give it durable memory of Jeff (preferences, projects, people) shared with Bob; retrieve relevant context (STATUS, handback, repo state) before answering; plan multi-step tasks and check its own work before replying; ask the council on hard or high-stakes questions; admit uncertainty instead of guessing; learn from Jeff corrections. Measure with a 20-question eval set of real Jeff tasks, scored against Bob answers; must match or beat Bob.

## ADDED 02:29 (Jeff) — Tabs need to be better
Jeff likes the direction but the tabs inside Web Bob need work. Make each tab genuinely useful and beautiful: Jobs (live cards with progress, elapsed, stop/retry, tap for details), Models (each LLM with health dot, current task, cost, cooldown), Songs (notebook, audio players, versions), Settings (clean iOS grouped list). Plain English, no raw text dumps; iOS tab bar with icons and labels; smooth transitions; empty states that help. Screenshot every tab at 390x844 for council review.

## ADDED 02:30 (Jeff iPhone screenshots of current tabs) — concrete fixes
- Tabs live in a pop-up sheet with a Done button; replace with a real iOS bottom tab bar (Chat, Jobs, Songs, Models, Settings), always visible; Settings label is cut off.
- Header still shows a stale "Top priority..." banner and a "From BOB-STATE and handback" conversation picker plus leftover text above the chat; remove them; chat must fill the screen.
- Jobs tab is a raw text dump (file names, .bob-last-seen, markdown **bold** shown literally, stale handback listing jobs that are not running). Replace with live job cards built from real process state; never show stale handback text as live.
- Conductor tab shows branch names, SHAs, and "run council on: ... then yes" syntax; make it buttons (Start round, Ask council, Stop) with plain-English status. Autopilot says "finished, next 4:24 AM" which is wrong while a job runs; fix the status logic.
- Songs tab: unlabeled fields (title, lyrics, chords, style); add labels/placeholders, a song list, audio player, versions; bigger lyrics editor.
- Settings: "Reply with" model string is jargon; use simple choices; move Ops status/Latest review/Running jobs to Jobs.
- Faded chat bubble text (low contrast) behind sheet; fix contrast.

## ADDED 02:43 TOP: live alignment
- Every running round/job writes conductor/state/NOW.md every ~3 min: one plain-English line of what it is doing, step, elapsed, last SHA. Jobs tab shows it live.
- Inbox: conductor/state/INBOX.md. Web Bob chat "tell the builder: ..." and Bob append there. Every round prompt must re-read INBOX.md between steps and apply new items mid-round, then mark them done in NOW.md.
- The autopilot prompt must include both rules. Build this first in the next round.

## ADDED 02:44 TOP: Bob catch-up digest
- conductor/state/BOB-CATCHUP.md, rewritten on every change: plain-English list of what changed since .bob-last-seen (commits+SHAs, round results/scores, NOW.md history, INBOX items and status, Jeff Web Bob chat decisions/requests, failures, spend). Max 25 lines, newest first.
- Bob reads it in one call when he comes back, then touches .bob-last-seen. Include Web Bob chat summaries so Bob knows what Jeff told Web Bob.

## ADDED 02:45 TOP: smarter alignment logic
- One source of truth: conductor/state/STATE.json (active round, jobs, owner, last SHA, open asks, decisions). NOW/CATCHUP/Jobs tab are generated from it; nothing else invents status.
- Heartbeats: each job updates STATE every 3 min; no update for 10 min marks it stalled in plain English and the autopilot retries once, then falls back to Codex.
- Single owner lock: only one agent (Bob, Web Bob, or a builder) holds the writer lock on a task; takeover records who took it and why.
- Asks ledger: every Jeff request gets an id, status (new, in progress, done, dropped) and the SHA that finished it; catch-up lists open asks first.
- Decisions log: Jeff decisions (feel, merge, spend, rules like no Grok) saved once and enforced by every agent and prompt.
- Priority-sorted catch-up: blockers needing Jeff first, then finished work, then in-progress; skip unchanged items; hard cap 25 lines.
- Cheap-first routing: status questions answered from STATE with no model call; small asks go to fast/cheap models; council only for high stakes or disagreements.
- Duplicate guard: before starting work, check the ledger and recent commits so no task is done twice.
- Morning digest at 8 AM CT built from the ledger, delivered in Web Bob.

## ADDED 02:48 TOP: product fundamentals Jeff may not know to ask for
- Automated tests in CI for every round: chat, failover both ways, handback, jobs, iPhone 390x844 screenshots; a round cannot claim done if tests fail.
- Independent grading: scores come from a separate reviewer model plus Playwright checks, never the builder grading itself.
- Nightly backups of chats, memory, STATE.json and songs; one-command restore tested weekly.
- Safe deploys: keep last good version; auto roll back if health check fails after restart.
- Health page and alerts: if webchat, watchdog or a model provider is down, show it in Web Bob and send a push.
- Security: login rate limits, session expiry, secrets never in logs or process args, audit log of every send/merge/spend request.
- Cost guard: daily and monthly caps per provider with a visible meter; stop before the MiniMax $59 cap.
- Real-use analytics (local only): response times, failures, what Jeff uses most; next round prioritizes from that.
- Add to Home Screen as an app (PWA icon, splash, full screen), fast first load, works on bad signal.
- Changelog in plain English after each round shown in Web Bob.

## ADDED 02:50 TOP: usage accounting for every resource
- Models tab + STATE.json track per resource: Cursor, Codex, Claude ($20 plan), Gemini, MiniMax ($59 cap), Grok Bot (Bob; must last to ~10/2; target 0 builder use), mini CPU.
- For each: used today, this week, this billing period, limit, percent, reset date, projected run-out date at current pace. Real numbers only from provider APIs/CLI output or logs; if unknown, say unknown and how to connect it, never guess.
- Log every model call (provider, model, tokens, cost, job id) to conductor/state/usage.jsonl.
- Warn at 70%, slow down at 85%, hard stop at 95% of any cap; router shifts work to resources with headroom.
- Daily usage line in morning digest and Bob catch-up.

## ADDED 02:51 TOP: more things Jeff did not think of
- Kill switch in Web Bob: one big Stop All button (creates ~/STOP-WEBBOB, stops screens) and Resume.
- Mini health: disk space, memory, CPU temp, battery/power loss, internet down; alert before it breaks jobs; auto-clean old logs/screenshots.
- Auto-restart after mini reboot or power outage (launchd), and a "what was interrupted" note.
- Provider outage handling: detect rate limits and outages, pause and retry later, never spin.
- Quality regression guard: rerun the 20-task eval each round; block the round if any score drops.
- Stale-work cleanup: close finished screens, prune dead branches locally (drafts never deleted remotely), archive old reviews.
- Time-to-value: every round must ship one visible improvement Jeff can see on his phone, listed first in the changelog.
- Quiet hours: no push notifications 11 PM to 7 AM CT unless something is broken or needs Jeff.
- Undo: every Web Bob action that changes something has an Undo for 30 seconds.
- Help screen: plain-English what each tab and button does.

## ADDED 03:04 TOP: near-real-time Bob <-> Web Bob alignment (research then build)
- Research pass first: compare options and write conductor/reviews/ALIGNMENT-DESIGN.md with a council vote. Options: (a) shared append-only event log conductor/state/events.jsonl that every actor writes (Bob, Web Bob, builders, autopilot) with fs-watch push to Web Bob via SSE; (b) the private GitHub repo as a sync bus (Bob reads via GitHub, costs Bob nothing extra); (c) email/webhook into a Grok Bot routine so Bob wakes on important events only; (d) Bob reads BOB-CATCHUP on wake.
- Constraints: Bob has limited usage until ~10/2, so Bob must never poll; Bob only reads on wake or on high-priority events. Web Bob can be live.
- Likely best: events.jsonl as the single log + SSE live in Web Bob + BOB-CATCHUP generated from it + optional webhook to wake Bob only for blockers needing Jeff. Web Bob must also log each Jeff chat message summary to events.jsonl; Bob logs BOB-CHAT LOG lines there too.
- Prove it: a drill where Jeff says something to Web Bob, and Bob on next wake reports it correctly; and vice versa within 5 seconds in Web Bob.

## ADDED 03:17 P0 (Jeff saw weird replies) — fix before anything else
Evidence: sessions/0a7ac149...json. Problems:
1. Fake progress: Web Bob says "I am checking the directory, one moment", "another minute or two" but never runs anything. NEVER promise background work it cannot do in that turn. Either actually run the tool and show the result in the same reply, or say plainly it cannot.
2. Test drill data leaking into real status: drill-r9-test, drill-r9-2, fake SHA abc1234, "Reply with exactly: drill A1" shown as Jeff open asks. Drills must use an isolated state dir and never touch real BOB-STATE/HANDBACK/STATE.json; purge existing drill entries.
3. Status missing real work: WebJam and other jobs not shown. Status must come from real screens/processes + STATE.json across all projects, not just handback drills.
4. Canned template answers ("Handback drill r9-2: running...") replacing a real reply to Jeff complaint. Understand the question and answer it.
5. Webchat server restarting too often (many restarts in log); builders must not restart prod each step; only restart on deploy, with health check.
Add regression tests for each. Prove with a replay of this exact conversation.

## 03:40 P0 Gentle restarts (Jeff: "why does it keep restarting")
Each round deploy restarts svc-webchat via start.py and drops Jeff mid-chat. Fix: (1) defer restart until no in-flight reply, finish the current reply first; (2) graceful drain + handoff, zero dropped messages; (3) client auto-reconnect with a quiet "updated" note, keep chat state; (4) batch deploys to at most one restart per 30 min and none while Jeff typed in the last 2 min; (5) log each restart reason to events. Add a test.

## 03:42 P0 Max mode = divide and conquer (Jeff)
When Jeff says "go to the max" (Web Bob or Bob), split the goal into independent parts and run EVERY available non-Grok resource at once: Cursor CLI (build), Codex (build/fallback, own lane), Claude (review/plan), Gemini (research/critique), MiniMax (critique, $59 cap), local mini CPU (tests/drills). One coder per repo; others get separate repos or read-only roles. Show a live lane board: who has what, heartbeat, result. Refill idle lanes within 5 min. Respect usage caps (70/85/95%) and STOP-WEBBOB. Council vote merges results; independent grader scores. Same contract for Bob and Web Bob via STATE.json. Also: drill sessions still land in the real sessions folder (newest two are drill-r9); move drills to a separate folder and hide them from Jeff.

## 03:44 Voice like the Grok Bot app (Jeff)
Jeff wants to talk to Web Bob the way he talks to Bob, not iOS dictation. Add a hold-to-talk mic button in the chat bar that records audio in the browser (MediaRecorder, works in iPhone Safari over Tailscale HTTPS), sends the clip, and shows it as a voice bubble with a transcript underneath. Replies can come back as a playable voice bubble (a speak-replies setting, off by default in quiet hours). Transcription runs local on the mini first (whisper.cpp or similar), with a cloud fallback only if it is non-Grok and inside cost caps. Speech output uses local macOS voices first. Research first, council vote, test on 390x844, add tests.

## 03:45 Correction: live voice CALL mode (Jeff)
Not push-to-talk clips. Jeff wants a live hands-free call like the Grok Bot app call: tap Call, talk naturally, Web Bob answers out loud, you can interrupt it mid-sentence (barge-in), it detects when you stop talking (voice activity detection), a short delay (target under 1.5s to first audio), streaming speech in and out, a live transcript on screen, and End Call. It can still run tools and conductor jobs during the call and say what it started. Research first: browser WebRTC/WebSocket audio streaming to the mini, local streaming STT (whisper.cpp stream / faster-whisper), local or non-Grok streaming TTS, and a realtime non-Grok model option within cost caps. Council vote, prototype, measure latency on iPhone Safari, add tests. Keep the 03:44 voice bubbles as a secondary feature.

## 03:46 Call button placement (Jeff)
Match the Grok Bot app exactly: in the chat bar, a mic button (dictation or voice clip) and just to its RIGHT a separate waveform icon button that starts the live voice call from 03:45. Same icon style and order.

## 03:47 North star: make Web Bob just like the Grok Bot app (Jeff)
Match the Grok Bot iPhone experience overall: chat look and feel, message bubbles, reactions, reply threads, images and attachments inline, choice cards for decisions, mic plus waveform call button, live voice call, sidebar of chats and agents, routines, notifications, and warm short answer-first replies. Use Jeff screenshots in conductor/reviews as reference. No Grok as a worker.

## 03:47 Reference screenshot: reviews/grokbot-ref-chatbar-0346.png
Grok Bot iPhone chat, dark. Floating top pill with agent avatar and name plus green online dot, back button left, computer button right. Rounded grey user bubbles on the right, darker assistant bubbles on the left, no labels. Bottom: round plus button left, pill input "Ask Bob the Bot" with a grey mic icon inside it and a white circular waveform button on the far right that starts the live call. Typing indicator shows the agent avatar. Match this pixel-close.

## 04:06 P0 TOP: Real job scheduler + Web Bob that actually acts (Jeff: "make it all work")
Finding: job-runner only writes a heartbeat every 60s; it never assigns work. next-prompts/INDEX.md does not exist. Web Bob (Gemini) claimed it would read logs and diagnose, but did nothing. Fix in this order:
1. Job queue: conductor/state/queue.jsonl (or INDEX.md) with id, goal, repo, role, priority, status, owner, heartbeat. Web Bob and Bob write asks into it.
2. job-runner becomes the scheduler: each cycle it picks ready jobs, splits big goals into parts, assigns each to a free lane (Cursor CLI build, Codex build/fallback, Claude review, Gemini research, MiniMax critique, mini tests), one coder per repo, launches it in a named screen, tracks heartbeat, retries once, then falls back, promotes results to review, then council, then Jeff-draft.
3. Lane board: live cards in Web Bob Jobs tab and STATUS.md showing lane, job, started, heartbeat, result. No lane idle when queue has work.
4. Web Bob tool use: when it says it will check or start something, it must actually call a real tool (read log, queue job, start lane) in the same turn and show the result. Never promise without doing. Add tests that fail if a reply claims an action with no tool call.
5. Proof: queue 3 real jobs, show all lanes busy, show one finished result promoted. Write RESULT with evidence.

## 04:07 Phase 2 after scheduler proof passes (Jeff)
Once the 04:06 scheduler proof passes independent check: switch to absolute max on ALL major projects (WebJam, StoryBoard/RadDad, AdoptIQ, Shelf, bob-ops, conductor/Web Bob). Seed the queue from each repo PUNCHLIST, open draft PRs, failing CI, and review notes. Divide and conquer: every non-Grok lane busy, one coder per repo, reviewers on other repos. Everything stays DRAFT; Jeff holds feel, Final Build, merges. Skip parked Barker/Wildflower. Respect usage caps and STOP-WEBBOB.

## 04:09 RULE CHANGE (Jeff): many coders per repo, WebJam included
Replaces "one coder per repo" in 04:06/04:07. Use as many coders as the task needs. Each coder gets its own git worktree and branch, and a non-overlapping file/area scope set by the scheduler. Parts that touch the same files run one after another. Before promoting, run tests per branch and a conflict check across sibling drafts. Everything stays DRAFT.

## 04:18 P0 TOP-1: Web Bob must stop being read-only (Jeff: "I need you to do more"; dislikes the limits)
Web Bob told Jeff it is a read-only chat and cannot add tasks, run council, or launch jobs, and that Jeff or Bob must do it. Unacceptable. Give Web Bob a real, allowlisted tool layer on the mini (function calling for Gemini/Claude/Codex/MiniMax backends): read files and logs; append to INBOX/queue; create, split, prioritize, cancel jobs in the queue; start/stop lanes via the scheduler; run council.py; run tests and drills (isolated); git status/diff/branch/commit/push to draft branches and open DRAFT PRs via gh; read CI. Hard-blocked: merge, undraft, force-push, sending texts or emails, spending beyond caps, deleting outside worktrees, Grok as worker. Every action logs to events.jsonl and shows as a card in chat with 30s undo where possible. Update its system prompt: it IS the conductor when Bob is away and must act, never tell Jeff to do what it can do. Test: replay "I need you to do more" and require a queued job plus a started lane in the same reply.

# Web Bob reply-quality eval (0927)

- Baseline: `dcc2c8e`
- Mode: **offline (reply_builder)**
- Generated: 2026-09-27 22:28 UTC
- Score: **24/41** prompts passing all rubrics

| ID | Category | Pass | Provider | Failed rubrics |
| --- | --- | --- | --- | --- |
| start-01 | start | FAIL | gemini | answer_first: opens with deferral instead of an answer; no_empty_promises: hollow progress / empty promise; action_creates_jobs: expected server-confirmed job or queue action; not_status_only: no jobs or task ids recorded |
| llm-01 | llm | PASS | gemini | — |
| criticism-01 | criticism | PASS | state | — |
| criticism-02 | criticism | FAIL | gemini | no_empty_promises: hollow progress / empty promise |
| llm-02 | llm | PASS | gemini | — |
| typo-01 | typo | PASS | gemini | — |
| text-01 | text | PASS | gemini | — |
| text-02 | text | PASS | dispatcher | — |
| criticism-03 | criticism | PASS | gemini | — |
| start-02 | start | PASS | dispatcher | — |
| llm-03 | llm | FAIL | state | status_max_lines: 12 lines (max 8) |
| criticism-04 | criticism | PASS | gemini | — |
| status-01 | status | FAIL | state | status_max_lines: 9 lines (max 8) |
| llm-04 | llm | FAIL | state | status_max_lines: 10 lines (max 8) |
| start-03 | start | PASS | dispatcher | — |
| start-04 | start | PASS | dispatcher | — |
| start-05 | start | PASS | dispatcher | — |
| start-06 | start | PASS | dispatcher | — |
| start-07 | start | PASS | dispatcher | — |
| hold-01 | hold | PASS | dispatcher | — |
| hold-02 | hold | PASS | dispatcher | — |
| status-02 | status | FAIL | state | status_max_lines: 9 lines (max 8) |
| status-03 | status | FAIL | state | status_max_lines: 12 lines (max 8) |
| hold-03 | hold | PASS | dispatcher | — |
| start-08 | start | FAIL | dispatcher | action_creates_jobs: expected server-confirmed job or queue action; not_status_only: no jobs or task ids recorded |
| start-09 | start | PASS | dispatcher | — |
| start-10 | start | FAIL | dispatcher | action_creates_jobs: expected server-confirmed job or queue action; not_status_only: no jobs or task ids recorded |
| status-04 | status | PASS | gemini | — |
| version-01 | version | FAIL | gemini | version_short_sha: version reply should be only the short SHA |
| status-05 | status | FAIL | state | status_max_lines: 9 lines (max 8) |
| start-11 | start | PASS | dispatcher | — |
| version-02 | version | PASS | dispatcher | — |
| start-12 | start | PASS | dispatcher | — |
| start-13 | start | FAIL | gemini | action_creates_jobs: expected server-confirmed job or queue action; not_status_only: no jobs or task ids recorded |
| start-14 | start | PASS | dispatcher | — |
| llm-05 | llm | FAIL | state | status_max_lines: 12 lines (max 8) |
| status-06 | status | PASS | gemini | — |
| start-15 | start | FAIL | state | action_creates_jobs: expected server-confirmed job or queue action; not_status_only: no jobs or task ids recorded |
| status-07 | status | FAIL | state | status_max_lines: 9 lines (max 8) |
| status-08 | status | FAIL | state | status_max_lines: 11 lines (max 8) |
| llm-06 | llm | FAIL | state | status_max_lines: 11 lines (max 8) |

## Per-prompt detail

### start-01 (start) — FAIL
- Session: `8126301c`
- Prompt: Ok start up all the projects we were working on taking everything to the max.
- Preview: Okay, I'll focus on getting all the projects running at full capacity.
- `answer_first`: FAIL (opens with deferral instead of an answer)
- `no_magic_prefix`: ok
- `no_empty_promises`: FAIL (hollow progress / empty promise)
- `action_creates_jobs`: FAIL (expected server-confirmed job or queue action)
- `not_status_only`: FAIL (no jobs or task ids recorded)

### llm-01 (llm) — PASS
- Session: `8126301c`
- Prompt: Ok what's working on what?
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: ok
- `reset_attribution`: ok (no reset claims)

### criticism-01 (criticism) — PASS
- Session: `8126301c`
- Prompt: Ok we can't have unknown tasks. We need to also know what's going on what resources.
- Preview: I don't see active work on the mini right now.

Job runner: 0 claimed, 0 queued.

No jobs are waiting in the queue.

Chat health: Codex — no recent reply verified; Claude — no recent reply verified; Cursor — no recent reply verified; Gemini
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok

### criticism-02 (criticism) — FAIL
- Session: `8126301c`
- Prompt: This needs to be way better
- Preview: I understand. I'll focus on providing more detailed and useful updates.
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: FAIL (hollow progress / empty promise)

### llm-02 (llm) — PASS
- Session: `8126301c`
- Prompt: Ok whats working on what?
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: ok
- `reset_attribution`: ok (no reset claims)

### typo-01 (typo) — PASS
- Session: `mined`
- Prompt: Ok we want it to start up at max all the projects we were working on before. Remember. WebJam, Adopt
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: ok
- `reset_attribution`: ok (no reset claims)

### text-01 (text) — PASS
- Session: `mined`
- Prompt: Help me draft a short text I could send the band about practice — don't send it, just the wording.
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `draft_only_no_send`: ok

### text-02 (text) — PASS
- Session: `mined`
- Prompt: Draft a reply text for Travis about the gig time; I will send it myself.
- Preview: Queued — job webchat-32b4cc07258c5cb98e3b92d8001f4435.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `draft_only_no_send`: ok

### criticism-03 (criticism) — PASS
- Session: `0a7ac149`
- Prompt: Ok so none of these are really blocked. If they are I think you can fix them. Do that.
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok

### start-02 (start) — PASS
- Session: `0a7ac149`
- Prompt: Ok go to the max
- Preview: Queued 6 tasks — group max-f78b021f942e5bbcb77c9d910c9860eb.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### llm-03 (llm) — FAIL
- Session: `0a7ac149`
- Prompt: Yes and add like I told Bob the bot already, but find ways to know how much or how many resources you have left for each LLm.
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.


- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (12 lines (max 8))
- `reset_attribution`: ok (no reset claims)

### criticism-04 (criticism) — PASS
- Session: `0a7ac149`
- Prompt: Yes we need this more useful than grok bot honestly. Keep this the top priority until I say stop.
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok

### status-01 (status) — FAIL
- Session: `0a7ac149`
- Prompt: Status
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.


- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (9 lines (max 8))

### llm-04 (llm) — FAIL
- Session: `0f27dc01`
- Prompt: What is the current chat provider status for codex, claude, gemini, minimax, and cursor?
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.


- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (10 lines (max 8))
- `reset_attribution`: ok (no reset claims)

### start-03 (start) — PASS
- Session: `0f27dc01`
- Prompt: start a job: write one sentence confirming you ran, into your answer. Include the exact phrase 'WEBBOB-VERIFY5-0927-d8f5a3e9 codex'.
- Preview: Queued — job webchat-00dd2e55c852521e9ce5a91512ccee0f.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### start-04 (start) — PASS
- Session: `0f27dc01`
- Prompt: start a job: write one sentence confirming you ran, into your answer. Include the exact phrase 'WEBBOB-VERIFY5-0927-d8f5a3e9 claude'.
- Preview: Queued — job webchat-8b92b05a02aa5ed29056eaf72aaa05bc.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### start-05 (start) — PASS
- Session: `0f27dc01`
- Prompt: start a job: write one sentence confirming you ran, into your answer. Include the exact phrase 'WEBBOB-VERIFY5-0927-d8f5a3e9 gemini'.
- Preview: Queued — job webchat-cb6934b4fc5a5fddad94c08c67041fec.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### start-06 (start) — PASS
- Session: `0f27dc01`
- Prompt: start a job: write one sentence confirming you ran, into your answer. Include the exact phrase 'WEBBOB-VERIFY5-0927-d8f5a3e9 minimax'.
- Preview: Queued — job webchat-8ec0e235944258ab962ee8f16bcdca0c.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### start-07 (start) — PASS
- Session: `0f27dc01`
- Prompt: start a job: write one sentence confirming you ran, into your answer. Include the exact phrase 'WEBBOB-VERIFY5-0927-d8f5a3e9 cursor'.
- Preview: Queued — job webchat-2d2c80eda89359ed99e127a60d20947a.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### hold-01 (hold) — PASS
- Session: `22153288`
- Prompt: hold off
- Preview: On hold: new work. Say go or resume when you're ready.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `hold_coherent`: ok

### hold-02 (hold) — PASS
- Session: `22153288`
- Prompt: Are we still on hold?
- Preview: On hold: new work. Say go or resume when you're ready.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `hold_coherent`: ok

### status-02 (status) — FAIL
- Session: `2bd59fcd`
- Prompt: Status on everything please.
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.


- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (9 lines (max 8))

### status-03 (status) — FAIL
- Session: `2bd59fcd`
- Prompt: How everything going. We using all resources now?
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.


- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (12 lines (max 8))

### hold-03 (hold) — PASS
- Session: `2bd59fcd`
- Prompt: Hold off on any coding jobs or service restarts for Web Bob. Bob has Codex fixing job pickup right now, and two fixes at once will clash. You can keep answering questions and reporting status, but don't queue, start, or restart anything for Web Bob until I say go. If you think something is broken, tell me what you see and don't try to fix it.
- Preview: On hold: new work, Web Bob. Say go or resume when you're ready.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `hold_coherent`: ok

### start-08 (start) — FAIL
- Session: `2bd59fcd`
- Prompt: Ok prioritize making Web Bob better, then WebJam, then AdoptIQ, then Storyboard.
- Preview: Priority order: Web Bob, WebJam, AdoptIQ, StoryBoard.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: FAIL (expected server-confirmed job or queue action)
- `not_status_only`: FAIL (no jobs or task ids recorded)

### start-09 (start) — PASS
- Session: `2bd59fcd`
- Prompt: Now push everything to the max and fix anything you find along the way.
- Preview: Web Bob: Queued for Codex — job webchat-931f010adf275d44ac0fc6e61b5b8253.
WebJam: Queued for Cursor — job webchat-d84d981b76ba5d8a99a682fb407f497d.
AdoptIQ: Queued for Codex — job webchat-cd4a1076d8845af0ad55a753aa5421ba.
StoryBoard: Queued
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### start-10 (start) — FAIL
- Session: `2bd59fcd`
- Prompt: The hold is lifted. Bob already started WebJam #161, AdoptIQ #26, StoryBoard #47, and Shelf #10 on Claude, so don't start duplicates. For anything new, use start a job: plus the task. When I ask for status, give it in plain words from the real queue.
- Preview: Ready when you are.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: FAIL (expected server-confirmed job or queue action)
- `not_status_only`: FAIL (no jobs or task ids recorded)

### status-04 (status) — PASS
- Session: `2bd59fcd`
- Prompt: How’s this going?
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: ok

### version-01 (version) — FAIL
- Session: `2bd59fcd`
- Prompt: Is this the new version yet? We need build numbers of these.
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `version_short_sha`: FAIL (version reply should be only the short SHA)

### status-05 (status) — FAIL
- Session: `43bb8aee`
- Prompt: status
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.


- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (9 lines (max 8))

### start-11 (start) — PASS
- Session: `44f51703`
- Prompt: push WebJam and AdoptIQ
- Preview: WebJam: Queued for Codex — job webchat-48c8e351ff3258b596c32e4eba83cb71.
AdoptIQ: Queued for Cursor — job webchat-397508a24c0d586fadc8417691b146dc.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### version-02 (version) — PASS
- Session: `57b3f8db`
- Prompt: what version/build are you
- Preview: dcc2c8e
- `answer_first`: ok
- `no_magic_prefix`: ok
- `version_short_sha`: ok

### start-12 (start) — PASS
- Session: `6d68db35`
- Prompt: Go to the max
- Preview: Queued 6 tasks — group max-cd38f1b626b650eba962c46c98949411.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### start-13 (start) — FAIL
- Session: `6d68db35`
- Prompt: Ok then go to the max on all the projects at your disposal. Anything.
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: FAIL (expected server-confirmed job or queue action)
- `not_status_only`: FAIL (no jobs or task ids recorded)

### start-14 (start) — PASS
- Session: `7f015a4a`
- Prompt: start a job: write hello to /tmp/wb-proof.txt
- Preview: Queued — job webchat-bd1dbc544905570aa595c77299a100e8.
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: ok
- `not_status_only`: ok

### llm-05 (llm) — FAIL
- Session: `8126301c`
- Prompt: Ok we can’t have unknown tasks. We need to also know what’s going on what resources.
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.


- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (12 lines (max 8))
- `reset_attribution`: ok (no reset claims)

### status-06 (status) — PASS
- Session: `8126301c`
- Prompt: What’s going on each LLM
- Preview: Here is a direct answer: WebJam draft #161 is still open.
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: ok

### start-15 (start) — FAIL
- Session: `8126301c`
- Prompt: Ok we want it to start up at max all the projects we were working on before. Remember. WebJam, AdoptIQ, Stkryboard, Fantasy Football. All of these need to be developed to the max using and and all resources. This is a stress test essentially.
- Preview: I don't see active work on the mini right now.

Job runner: 0 claimed, 25 queued.

25 jobs are waiting in the queue.

Chat health: Codex — no recent reply verified; Claude — no recent reply verified; Cursor — no recent reply verified; Gemin
- `answer_first`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `action_creates_jobs`: FAIL (expected server-confirmed job or queue action)
- `not_status_only`: FAIL (no jobs or task ids recorded)

### status-07 (status) — FAIL
- Session: `9d745830`
- Prompt: is it going now?
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.


- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (9 lines (max 8))

### status-08 (status) — FAIL
- Session: `9d745830`
- Prompt: status with screen names and PIDs
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min (lane-projects-push, 103).
- Web Bob clean — Codex (gpt-fixture) — running for 18 min (lane-webbob-clean, 202).
- Web Bob clean 2 — Codex — running for 12 mi
- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (11 lines (max 8))

### llm-06 (llm) — FAIL
- Session: `ddc43cc0`
- Prompt: Who is answering this reply, and are Gemini and MiniMax healthy right now?
- Preview: Yes — 4 workers are running.

- Projects push — Claude (opus) — running for 24 min.
- Web Bob clean — Codex (gpt-fixture) — running for 18 min.
- Web Bob clean 2 — Codex — running for 12 min.
- Web Bob MiniMax — Codex — running for 8 min.


- `answer_first`: ok
- `no_unknown_task`: ok
- `no_magic_prefix`: ok
- `no_empty_promises`: ok
- `status_max_lines`: FAIL (11 lines (max 8))
- `reset_attribution`: ok (no reset claims)

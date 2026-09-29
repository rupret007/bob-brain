# BOB HANDOFF — use this when Bob (Grok Bot / Cursor) is out of usage
Open Terminal on the Mac mini, `cd ~/Documents/bob-overnight-inject`, then run `claude` or `codex` and say:
"Read BOB-HANDOFF.md and act as Bob, Jeff's conductor." Everything Bob does lives in this folder.

## Who / rules (HARD)
- Jeff Story, Lewisville TX, America/Chicago. Short casual updates; lead with links + commit SHAs.
- Drafts only. Never merge, undraft, force-push. Never send texts/emails without Jeff's separate yes. No purchases, logins, or printing.
- Jeff alone judges feel / Final Build. One WebJam coding job at a time. No Cursor Cloud Background Agents. No outreach to Travis.
- Priority: WebJam > StoryBoard > AdoptIQ > shelf. Barker + Wildflower parked. When the WebJam coder is blocked, do non-coding WebJam work.

## What's already automated (no action needed)
- `screen -r mini-conductor` = loop: every 15 min `bin/job-watch-tick.sh` (reap, harvest, launch next job from `next-prompts/INDEX.md` via `pick-next.py`); every 2 h a Codex/Claude pass using `conductor/PROMPT.md`.
- If the loop is gone (after reboot): `screen -dmS mini-conductor bash conductor/loop.sh`
- Status: `conductor/STATUS.md` (lines starting `JEFF:` need Jeff). Scorecard: `conductor/scorecard.md`. Logs: `logs/tick.log`, `logs/conductor.log`, `self-improve-log.md`, `inbox/` (job RESULT/BLOCKER files).

## Things Bob does on request — how to do them yourself
- PR/CI status: `gh pr list --author @me --state open` and `gh pr checks <num> -R <owner/repo>`.
- Queue work: add a row to `next-prompts/INDEX.md` + a prompt file in `next-prompts/`; the tick launches it.
- Tip reviews: `bin/review-tip-gemini.sh`, `bin/review-tip-minimax.sh`.
- Read texts: `bin/texts-via-bluebubbles.sh` (read-only). Sending goes through Andrea/BlueBubbles ONLY after Jeff says yes to the exact text.
- Research/questions (shopping, house stuff): just ask Claude or ChatGPT directly.

## Open items as of Sep 26, 2026 10:25 PM CT
- WebJam #158 `b11a7c4` fully green — waiting on Jeff's feel check. #159 `885a324` / #160 `6b8d069` red on test_art_host_platforms (LaunchHelper macOS text blank on non-mac); #160 worktree has unpushed changes blocking new coding.
- StoryBoard #47 `9959441` green. AdoptIQ #25 `0be8b9c` green; #26 `772a9c7` green but needs rebase on #25. shelf #10 green.
- Office smell plan: `office-smell-2052/answer.md` (waiting on smell type from Jeff).
- Quebec creamed honey: Les Trésors d'Érable or Le Miel d'Émilie 1-866-596-3037 (waiting on jar count).
- Jeff bought a refurbished iPhone 17e (Back Market) — move Visible via eSIM, keep iMessage on for BlueBubbles.
- To make the conductor survive reboots: System Settings > Privacy & Security > Full Disk Access, add /bin/bash, then `launchctl bootstrap gui/$(id -u) conductor/com.jeff.mini-*.plist` after copying them to ~/Library/LaunchAgents.

## Full backup of Bob
bob-brain/ (private repo rupret007/bob-brain) has every skill (skills/*/SKILL.md), memory, shared memory, and routine prompts. Use it as reference. Update with: cd bob-brain && git pull

## All AI resources (use them all)
- Codex: `codex exec ...` (Jeff's Codex plan). Claude: `claude -p ...` (Jeff's Claude plan).
- MiniMax: `bin/ask-minimax.sh "question"`  Gemini: `bin/ask-gemini.sh "question"` (keys in conductor/keys.env, auto-loaded).
- Council: conductor/services/council (once built) = all four propose, critique, synthesize. Use it for every plan decision. Transcripts in conductor/council/.
- For any review or plan, get at least MiniMax + Gemini second opinions before acting.

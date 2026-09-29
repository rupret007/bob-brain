# Bob web chat (Jeff: "a website I can type into, just like the Grok Bot chat")
Build conductor/webchat/: a small Python (stdlib or FastAPI if already installed) web app on the mini.
- Chat UI like a messenger: message history, typing box, streaming or polling replies, mobile-friendly, dark mode.
- Each user message goes to `codex exec` (ChatGPT plan) with the system context "Read BOB-HANDOFF.md + bob-brain/ and act as Bob". Keep the conversation in a session file so it has continuity (resume codex session if supported; otherwise pass the last N turns). Fallback order: codex, then cursor-agent --trust, then gemini (bin/ask-gemini.sh). Claude is only the $20 plan, so never make it the default.
- Buttons: "status" (renders conductor/STATUS.md), "Gemini review" (reviews/LATEST.md), and a jobs list (screen -ls plus the queue).
- SECURITY: bind to 127.0.0.1:8787 only. Require a login: a random password stored in conductor/webchat/.password (chmod 600), shown to Jeff via Bob. Session cookie HttpOnly. No public exposure. For access off the home network, document Tailscale (tailscale serve) as the recommended path; do not open router ports. Same hard rules: drafts only, no merges/undrafts/force-push, no texts/emails without Jeff's yes.
- Add a LaunchAgent plist (com.jeff.bob-webchat) to conductor/launchd/ and have install.sh include it.
- Start it now in a screen (svc-webchat), verify with curl (login page 200, unauthenticated /api 401), and write the URL + password location to reviews/WEBCHAT-RESULT.md. Add it to BOB-HANDOFF.md and ~/Desktop/HOW-TO-REACH-BOB.md.

## UPDATE 23:08 CT (Jeff: "work as well as Grok Bot Bob, use all the resources")
- Bob-in-browser must be a full conductor, not just a chatbot. It can run shell commands on the mini, read and write files, use gh (draft PRs), check and queue jobs in services/jobs.py, and start and stop screen jobs. Every message goes to codex exec with full tool access in the bob-overnight-inject dir.
- Route by task: Codex does orchestration and coding. Cursor does coding and second opinions. Gemini 3.1 Pro does deep review and long context. MiniMax does UI/UX critique (within the cap). Claude does short critiques only ($20 plan). For big asks, run the council (propose, critique, synthesize) and show which models answered.
- Features like Grok Bot: attach files and images, clickable links, memory (append durable facts to bob-brain memory), a standing-rules reminder, and action cards that need Jeff to confirm before anything risky (merges, undrafts, sends, spending) happens. It never does those without a click.
- Show live progress (streaming, or a steps log) and a lanes panel with busy/idle status and spend for each model.

## UPDATE 23:09 CT (Jeff: "the same logic as you")
- Bob-in-browser must follow the same logic Grok Bot Bob uses. Load it as the system prompt from bob-brain/: profile, memory, user-memory, skills, routine prompts. Also load conductor/BOB-OPERATING-RULES.md, which you write by distilling the behaviors: answer first, keep it short and casual, lead with links and SHAs, act rather than ask on reversible work, confirm before anything risky, never fabricate, drafts only, no texts or emails without a separate yes, one WebJam coder, priority WebJam > StoryBoard > AdoptIQ > shelf, delegate heavy work to lanes, and report the real state honestly. Reload it every message so updates from bob-brain take effect.

## UPDATE 23:10 CT (Jeff: "make it amazing")
- Quality bar: polished, delightful, fast. Clean modern design (think iMessage/Linear), smooth streaming, markdown and code rendering, drag-and-drop attachments, keyboard shortcuts, installable PWA on the iPhone home screen, voice input via the browser mic. After building, have MiniMax (within the cap) and Gemini critique the UI, then do one polish pass on their top 5 points. Log the before/after in WEBCHAT-RESULT.md.

## UPDATE 23:13 CT (Jeff: "take code from places if you need to")
- Reuse proven open-source chat UIs and parts instead of hand-rolling: e.g. Open WebUI, LibreChat, or assistant-ui / Vercel AI chatbot patterns, marked + highlight.js, etc. Permissive licenses only (MIT/Apache/BSD), and keep the attribution and LICENSE files. Also reuse ~/Andrea_NanoBot pieces where they fit (read-only copy, never modify it). Pick whichever gets the best result fastest; the backend must still use our codex/cursor/gemini/minimax lanes and Bob rules.

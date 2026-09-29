Based on the provided parity audit document, here are the top 15 concrete gaps in Web Bob compared to Bob the Bot, ranked by user impact.

---

### Top 15 Capability Gaps: Web Bob vs. Bob the Bot

#### 1. Sending iMessage/SMS via Gated Relay
**Impact:** High. The inability to act on communication is the single largest functional gap, preventing Web Bob from closing the loop on conversational tasks.
*   **Gap:** Web Bob is explicitly forbidden from sending texts and has no code path to interact with the Andrea NanoBot relay. Bob the Bot is designed to use this relay (mediated by Jeff's approval).
*   **Acceptance Check:**
    *   **Given** Web Bob has presented a text message draft for "John Appleseed" with the content "See you at 5pm".
    *   **When** Jeff provides a distinct, separate confirmation in the chat UI (e.g., clicking a "Send" button or typing an exact phrase like `send it now`).
    *   **Then** the message must be sent to John Appleseed via the Andrea NanoBot relay, and an audit log must record that Jeff approved this specific text at this time.

#### 2. Drafting iMessage/SMS
**Impact:** High. Without the ability to compose drafts, the entire texting workflow is a non-starter. This is a prerequisite for sending.
*   **Gap:** Web Bob has no functionality for composing a text message draft in response to a user request (e.g., "tell my wife I'm on my way home").
*   **Acceptance Check:**
    *   **Given** Jeff's most recent text from Jane is "Are you heading home soon?".
    *   **When** Jeff types "draft a reply saying I'll be home in 20 minutes".
    *   **Then** Web Bob must display a distinct UI element (a "draft card") containing the proposed recipient ("Jane") and message ("I'll be home in 20 minutes"), clearly marked as an unsent draft.

#### 3. Reading and Summarizing iMessage/SMS
**Impact:** High. Lacking situational awareness of recent conversations severely limits Web Bob's usefulness as a proactive assistant.
*   **Gap:** Web Bob cannot access message history via `bin/texts-via-bluebubbles.py` and thus cannot answer questions like "did my mom text me back yet?".
*   **Acceptance Check:**
    *   **Given** there are three unread messages from "Delivery Service" in the BlueBubbles database.
    *   **When** Jeff asks Web Bob "summarize my recent texts".
    *   **Then** Web Bob must execute `bin/texts-via-bluebubbles.py` and respond with a summary that accurately reflects the content of the three unread messages.

#### 4. Writing to Durable Memory
**Impact:** High. A read-only memory prevents Web Bob from learning and adapting to user preferences, forcing the user to repeat information.
*   **Gap:** Web Bob can read `bob-brain/memory/profile.md` but has no code path to append new facts, unlike the desktop agent.
*   **Acceptance Check:**
    *   **Given** the user is in a chat session.
    *   **When** the user types "remember that I prefer to use Claude for creative writing tasks".
    *   **Then** Web Bob must confirm the exact fact to be saved, and upon approval, append a new line like `[2026-09-28] Jeff prefers to use Claude for creative writing tasks.` to the `bob-brain/memory/profile.md` file.

#### 5. Voice Interaction (Input/Output)
**Impact:** High. The lack of a voice modality makes Web Bob inaccessible for hands-free use cases, a core feature of many modern assistants.
*   **Gap:** The prompt explicitly lists "voice" as a Bob the Bot capability. Web Bob is a text-only web interface with no evidence of speech-to-text or text-to-speech integration.
*   **Acceptance Check:**
    *   **Given** the Web Bob UI is open in a browser that supports the Web Speech API.
    *   **When** the user clicks a microphone icon and says "what's on my schedule today?".
    *   **Then** the input field must be populated with the transcribed text, the request must be processed, and the resulting answer must be spoken aloud by the browser's TTS engine.

#### 6. Managing Other Agents
**Impact:** Medium-High. For a power user managing multiple AI processes, the inability to orchestrate them from the primary interface is a major workflow bottleneck. This is deliberately fenced off due to safety concerns.
*   **Gap:** Web Bob is explicitly prevented from invoking orchestration scripts like `services/start-all.sh` or `mini-conductor`. Bob the Bot's core design includes this capability.
*   **Acceptance Check:**
    *   **Given** no "council.py" agent is currently running.
    *   **When** Jeff types "start a new council review on the latest PR".
    *   **Then** Web Bob must, after a safety confirmation, execute the appropriate script to launch the `council.py` agent process. *(Note: This should not be implemented until the "Notable safety finding" is fully resolved.)*

#### 7. General-Purpose Web Search
**Impact:** Medium-High. Without access to real-time information from the web, the assistant's knowledge is limited to its training data, making it useless for many common queries.
*   **Gap:** Web Bob has no tool or capability for fetching information from public URLs. The document notes this is a shared gap but a critical assistant feature nonetheless.
*   **Acceptance Check:**
    *   **Given** the user is in a chat session.
    *   **When** the user asks "what was the score of the Mets game last night?".
    *   **Then** Web Bob must trigger a web search tool, find the correct score from a reliable source, and provide it in its response with a source link.

#### 8. User-Facing Personal Reminders
**Impact:** Medium. A core expectation for a personal assistant is the ability to set simple, time-based reminders.
*   **Gap:** Web Bob has no user-facing scheduling for personal reminders (e.g., "remind me at 6pm"), only internal system jobs.
*   **Acceptance Check:**
    *   **Given** the current time is 4:00 PM.
    *   **When** Jeff types "remind me to take out the trash at 5:00 PM".
    *   **Then** at 5:00 PM, a new message must appear in Jeff's active chat session from the assistant saying "Reminder: take out the trash".

#### 9. Viewing Status of Other Agents
**Impact:** Medium. Read-only status provides crucial operational visibility and is a safe, high-value first step toward full orchestration.
*   **Gap:** Web Bob cannot provide information about other running processes, whereas Bob the Bot relies on `bin/who-is-running.sh` for this.
*   **Acceptance Check:**
    *   **Given** a Claude agent and a Cursor agent are running.
    *   **When** Jeff asks "who is running right now?".
    *   **Then** Web Bob must display the formatted, human-readable output of `bin/who-is-running.sh`, showing the active Claude and Cursor processes.

#### 10. On-Demand Screenshots
**Impact:** Medium-Low. While not a daily-use feature, the ability to visually capture the state of the desktop on command is a powerful utility that is currently missing.
*   **Gap:** Web Bob's screenshot capabilities are for developer E2E tests only and cannot be triggered by the user from chat. Bob the Bot has a skill that uses `screencapture`.
*   **Acceptance Check:**
    *   **Given** an application window for "Calculator" is open on the desktop.
    *   **When** Jeff types "take a screenshot of the calculator app".
    *   **Then** Web Bob must capture an image of only the Calculator window and display it in the chat interface.

#### 11. Personal Task Assistance (e.g., Shopping)
**Impact:** Medium-Low. This extends the assistant's utility into real-world tasks, though it's a partial capability even for Bob the Bot.
*   **Gap:** Web Bob has no skills related to shopping research or initiating purchases. Bob the Bot has skills for Amazon and Domino's that operate with a human-in-the-loop payment gate.
*   **Acceptance Check:**
    *   **Given** Jeff asks "find me the link to buy a 12-pack of Paper Towels on Amazon".
    *   **When** the request is processed.
    *   **Then** Web Bob must return a direct Amazon URL to the product, along with its price, and state clearly that it cannot place the order itself.

#### 12. Native Desktop Integration
**Impact:** Medium-Low. A desktop assistant feels more integrated via system features like global hotkeys, which a web app cannot easily provide.
*   **Gap:** As a web app, Web Bob lacks native integration points. Bob the Bot, being a desktop assistant, exists within the user's terminal session and can be more easily scripted with system tools.
*   **Acceptance Check:**
    *   **Given** Web Bob is not the active application window.
    *   **When** the user presses a pre-configured global hotkey (e.g., `Cmd+Shift+B`).
    *   **Then** the Web Bob interface should become the active window with the chat input field focused.

#### 13. Surfacing GitHub CI Check Status
**Impact:** Low. This is a quality-of-life improvement for the existing coding workflow, not a new capability.
*   **Gap:** While both bots follow a "draft-only" PR rule, the document notes that `gh pr checks` is used manually with Bob the Bot. Web Bob does not surface this information.
*   **Acceptance Check:**
    *   **Given** a draft PR branch `feature-x` exists and its CI checks have failed.
    *   **When** Jeff asks "what's the status of the feature-x branch?".
    *   **Then** Web Bob's response must include the fact that it is a draft PR and explicitly state that the "CI checks have failed", ideally with a link to the check logs.

#### 14. Lack of a Formal "Draft + Confirmation" UI Pattern for All Actions
**Impact:** Low. This is a design pattern gap more than a feature gap, but it's key to Bob the Bot's "honest status" and safe operation.
*   **Gap:** Bob the Bot's texting skill uses a robust "draft+yes" flow. Web Bob lacks a generalized UI pattern for confirming any potentially impactful action (like writing to memory or running a script).
*   **Acceptance Check:**
    *   **Given** Web Bob is about to perform any action with a side-effect (e.g., saving a memory, running a command).
    *   **When** the action is proposed.
    *   **Then** the UI must render a standardized confirmation widget that clearly describes the action to be taken and requires a separate, explicit user interaction (e.g., a button click) to proceed.

#### 15. Lack of Explicit Build SHA/Version Information in UI
**Impact:** Low. For a developer-user, knowing the exact build you're interacting with is crucial for debugging and verification.
*   **Gap:** The prompt header lists a specific build SHA for Bob the Bot. The Web Bob parity doc lists a verified worktree, but there's no indication this is surfaced to the user in the chat UI itself.
*   **Acceptance Check:**
    *   **Given** the Web Bob application is running.
    *   **When** the user inspects the web UI.
    *   **Then** the commit SHA of the running build (`worktrees/webbob-e2e-0927`) must be visible somewhere on the page (e.g., in the footer or an "About" dialog).
# Web Bob gap implementation — 2026-09-27 (1725)

Branch: `draft/webbob-gaps-1725`  
Base: `dcc2c8e`  
Scope: top three non-text/voice/reply-status gaps from `conductor/reviews/WEBBOB-GAP-AUDIT-GEMINI-0927.md`.

## 1. Durable memory write (audit #4)

**Behavior:** `remember that …` proposes a fact with a confirmation card (`Save memory` / `yes, save memory`). On approval, appends a dated line to `bob-brain/memory/profile.md`.

**Code:** `webchat/bob_gaps.py`, `Chat.bob_gaps_memory_turn()` in `webchat/app.py`, memory action-card labels in `webchat/static/app.js`.

**Acceptance test:** `webchat/test_bob_gaps.py` → `MemoryGapTests.test_remember_requires_confirmation_then_appends_profile`

## 2. General-purpose web research (audit #7)

**Behavior:** Questions matching live-research patterns (e.g. “what was the score of the Mets game last night?”) call DuckDuckGo’s JSON API and reply with an answer plus source link when available.

**Code:** `webchat/bob_gaps.py` (`needs_web_search`, `web_search`, `format_web_search_reply`), `Chat.try_bob_gaps()` in `webchat/app.py`.

**Acceptance test:** `webchat/test_bob_gaps.py` → `WebSearchGapTests.test_mets_score_triggers_search_with_source_link`

## 3. On-demand screenshots (audit #10)

**Behavior:** `take a screenshot` / `take a screenshot of the <app>` runs macOS `screencapture` (window target via AppleScript when named), stores PNG under `conductor/webchat/captures/`, and renders it in chat via `/api/captures/<id>`.

**Code:** `webchat/bob_gaps.py`, capture route in `webchat/app.py`, image markdown in `webchat/static/app.js`, `.chat-capture` style in `webchat/static/style.css`.

**Acceptance test:** `webchat/test_bob_gaps.py` → `ScreenshotGapTests.test_calculator_screenshot_shown_in_chat`

## Verification

```bash
cd webchat && python3 -m unittest test_bob_gaps.py test_chat_intent.py -v
```

**Result:** pass (32 tests in local run).

## Not in this change

- iMessage/SMS, voice, agent orchestration, personal reminders scheduler, `who-is-running` surfacing, texting reply-status — excluded per task brief.
- No deploy, service restart, or live texting.

## Safety

- Draft-only posture unchanged; memory writes require explicit confirmation.
- Screenshots are local captures only; no auto-send.

# Web Bob Round 6 — research-first design note (iPhone-first pass)

**Date:** 2026-09-27 CT · **Round:** 6 (re-run on R7 base) · **No Grok**

## What exists today (research pass)

| Source | Borrow | Reject | Why |
|--------|--------|--------|-----|
| [Apple HIG — Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars) | Persistent bottom tabs with icons; one primary task per tab | Modal “Done” sheets for main navigation | Jeff’s screenshots showed sheet + status dumps crowding chat; tabs must stay visible |
| ChatGPT / Claude iOS | Chat fills viewport; ops in separate surfaces; sticky composer | Raw repo filenames in the conversation chrome | Web Bob is stdlib + vanilla JS — match feel without a framework |
| [LangGraph persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/) | `conductor/handback/` as checkpoint | Hosted thread store | Zero-loss Bob ↔ Web Bob on one mini |
| [OpenAI Agents handoffs](https://platform.openai.com/docs/guides/agents) | Read BOB-STATE + handback before acting | Multi-agent mesh | Draft-only local control |
| [PWA on iOS](https://developer.apple.com/documentation/webkit/promoting_apps_with_smart_app_banners) | `viewport-fit=cover`, 16px inputs, home-screen meta | Push without Jeff yes | Notifications deferred; layout + handback first |
| AI music (Suno/Udio/etc.) | Lyrics/chords notebook + local sketch WAV | MiniMax music API (410) | Jeff 02:00 — no new signups |

## R6 design choices (this build)

1. **iPhone-first:** Remove chat clutter (handback chip, conversation bar, ops sheet). Full-height **inline tab views** (Chat, Jobs, Songs, Models, Settings) with iOS-style icon tab bar.
2. **Jobs tab:** Live job cards only; conductor as plain-English status + action chips; handback as one paragraph (no markdown filenames).
3. **Failover:** Keep `request_id` handback idempotency from R7; handback drill tags `r6-1` / `r6-2` ×2.
4. **Self-improve:** Expose tick status on Settings via `/api/panel` → `self_improve` (launchd + last handback log line).
5. **Songs:** Labeled fields, project picker, taller lyrics editor; still local sketch only for audio.

## Council tie-break (preview)

Gemini + MiniMax: inline tabs over sheet; Claude: keep confirm-in-chat for conductor chips — **vote: inline tabs + chips unchanged**.

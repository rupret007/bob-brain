# Web Bob Audit — 2026-09-27

Read-only audit of Web Bob at `http://127.0.0.1:8787` and `https://jeffs-mac-mini.tail758ab4.ts.net`, tested the way Jeff would use it from a phone: login, chat replies, history, failover, tool actions, mobile layout, error handling. No app files were edited. Codex is fixing in parallel; this doc is findings only.

Method: direct HTTP/curl against both origins with a real session cookie + CSRF token (matching what the browser does), plus headless Playwright at iPhone 14 viewport (390×844) driving the real login flow and tab navigation, with computed-style/DOM probes to avoid guessing from stale screenshots. No destructive or write actions were taken against app code; only normal user actions (login, send message, cancel, logout, tab switches) were exercised against the already-running local server.

---

## Ranked defects

### 1. (Medium-High) Raw `**markdown**` leaks into the Jobs and Models tabs instead of rendering as text/bold
**Repro:**
1. Log in at `127.0.0.1:8787`, open the **Jobs** tab (or **Models** tab — same data).
2. Scroll to the score-tiles grid (Reliability / Speed / Mobile UX / …).
3. The fourth tile's label reads literally `**iPhone design**` (asterisks visible), not "iPhone design".
4. Scroll a bit further to "#2 in scheduler queue" — its body reads `**Why:** Draft PRs #159 and #160 are CI-red on one test...` with literal asterisks instead of a bolded "Why:".

**Evidence:** `GET /api/panel` returns these fields verbatim with markdown syntax still embedded:
- `.live_ops.scores[3].area = "**iPhone design**"`
- `.live_ops.queued_jobs[1].goal = "**Why:** Draft PRs #159 and #160 are CI-red on one test..."`
- `.round_changelog.line` and `.self_improve.last_round_changelog` contain the same `**iPhone design**` / bolded-number markdown.

Chat message bodies do render markdown correctly (bold, code spans, links all work in the transcript), so this is specific to the Jobs/Models "plain dashboard" rendering path, which appears to copy raw markdown-table cell text through to JSON without stripping/parsing it. Likely source: whatever writes the score/queue markdown (a review-round scorecard) used `**bold**` for emphasis on that one row/line, and the panel builder passes the cell text straight through.

**Impact:** Cosmetic but visible on every load of two of the five tabs — reads as broken/unfinished on a phone.

---

### 2. (Medium) Quick-action chip row on Chat has no scroll affordance and hard-clips the last visible chip against the "Less" toggle
**Repro (iPhone-14 width, 390px):**
1. Start a new chat (Settings → Start new chat, or the chat-bubble icon → new).
2. Tap "More" next to the quick chips row.
3. The row expands to show chips, but the container is narrower than the content (`scrollWidth: 665` vs `clientWidth: 305` in test) and there is no fade/gradient/arrow hint that it scrolls horizontally.
4. The last visible chip ("Repo status") is bisected exactly at the container edge — it reads "Rep" then is sliced off — and the "Less" label sits immediately against that cut edge with almost no gap, so it looks like a rendering glitch rather than a scrollable list.

**Impact:** Functionally the chips still work if the user discovers they can swipe, but on first load it looks broken. Not a new regression — this exact clipped pattern is also visible in the previously captured `webchat/evidence/iphone-r15/iphone-14-chat.png`, so it has persisted across at least one prior review round.

---

### 3. (Low) Activity/"catch-up" ticker text is truncated mid-word with no ellipsis
**Repro:** Jobs tab → "Bob catch-up" row, or the condensed one-line activity summaries built from recent turns.
**Evidence:** DOM text dump of the Jobs tab includes fragments like:
`"...ew a small code change and capture useful notes. Keep it brie (gemini) - What is 17 times 23?..."`
— the string starts mid-word ("ew a small code change...", clipped from "**review** a small code change...") and ends mid-word ("Keep it brie[f]"), with no leading/trailing "…" to signal truncation. Also seen in the "#2 in scheduler queue" card, whose body ends mid-sentence ("...applied the") with no indication more text exists.

**Impact:** Purely cosmetic, but a user unfamiliar with the internals could read this as corrupted data.

---

## Verified working (no defect found)

- **Login:** correct password → 303 + `Set-Cookie` with `HttpOnly; SameSite=Strict`, `Secure` added automatically when served over HTTPS (verified on the tailscale origin) and omitted on plain HTTP (127.0.0.1) — correct behavior, not a bug.
- **Wrong password:** clean 401 with a friendly message; **10 failures/60s trips a 429** lockout ("Too many login attempts. Wait one minute and try again.") — solid brute-force protection.
- **CSRF:** every `/api/*` POST requires `X-CSRF-Token` matching the session's token (constant-time compare); cross-site `Origin`/`Sec-Fetch-Site` requests are rejected with 403.
- **Host validation:** requests with an unrecognized `Host` header are rejected (403) — both `127.0.0.1:8787` and the tailscale hostname are correctly allow-listed.
- **Logout:** invalidates the session server-side immediately; subsequent `/api/session` calls 401 and `/` redirects to `/login`.
- **Chat replies:** sent a real question ("What is 17 times 23?") through the full pipeline — routed to Gemini, correct answer ("391"), ~1s round trip, status transitions `queued → done` correctly.
- **History:** `/api/conversations` and `/api/conversations/:id` return accurate, ordered transcripts; conversation list survives across logins.
- **Cancel:** cancelling an in-flight reply produces a clean `"Reply stopped."` assistant message with `status: cancelled` — no stuck "running" state.
- **Error handling:** verified clean, correctly-worded responses for: oversized message (>6000 chars) → 400; reused `request_id` → 400 ("already used for a different message"); invalid `provider` value → 400; bad/missing CSRF token → 403; cancel on a nonexistent conversation → 404; malformed JSON body → 400. No stack traces or raw exceptions leaked to the client in any case (dispatch has a catch-all that returns a generic 500).
- **Tool actions:** `/api/jobs`, `/api/handback`, `/api/panel`, `/api/status`, `/api/song-projects`, `/api/music/eligibility` all returned live, sane data reflecting the real running services (screens, spend caps, song drafts).
- **Failover:** all 5 provider lanes (`codex`, `cursor`, `gemini`, `minimax`, `claude`) currently report `state: ready`, so a live failure couldn't be organically observed today without deliberately breaking a provider (out of scope for a read-only audit). Historical drill evidence at `webchat/evidence/failover-live.json` (run 2026-09-27 00:something CT) shows correct cascading behavior for `codex→cursor`, `codex→cursor→gemini`, and `three-failures→minimax`, with accurate user-facing messages ("Codex hit its rate or usage limit; switched to Cursor.").
- **Mobile layout / contrast:** re-verified live (not from stale screenshots — see note below) that Chat, Jobs, Songs, Models, and Settings all render with correct dark-on-light text (`color: rgb(19,38,28)`, opacity 1) at 390px and 430px widths. No console or page errors during navigation across all five tabs.

---

## Process note: stale evidence screenshots misrepresent current state

`webchat/evidence/iphone-r15/{iphone-14-lanes-tab,iphone-14-settings-tab,iphone-14-song-tab}.png` (captured 2026-09-27 07:12) show severely washed-out, nearly illegible text — measured contrast of the darkest pixel in the "Settings"/"Songs"/"Models" title against its background was ~220 vs. ~244 brightness (roughly 1.1:1), versus ~120 vs ~239 (a real, readable contrast) in the same round's `iphone-14-chat.png` and `iphone-14-ops-tab.png`. I initially treated this as a live defect, but a fresh Playwright probe against the running server today shows all tabs currently compute `color: rgb(19,38,28)` at full opacity — i.e. **this is not reproducible right now**. Recommend regenerating the `iphone-r15` evidence set (or deleting it) before using it as release evidence, since in its current state it would either hide a real regression or wrongly suggest one to whoever reviews it next.

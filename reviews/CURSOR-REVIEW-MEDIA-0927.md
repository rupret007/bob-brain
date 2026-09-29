# Cursor read-only review — Web Bob media lane

**Worktree:** `wt-webbob-media-0927`  
**Branch:** `draft/webbob-media-0927`  
**Diff base:** `draft/webbob-clean-0927` (`cfea813` — Add Web Bob chat media attachments with vision and proof.)  
**Reviewed:** 2026-09-27  
**Scope:** Functional bugs, security (text send paths, secret leakage), mobile Safari UX, test gaps. **No code changes.**

---

## Summary

The media lane is generally well bounded (auth + CSRF on API, authenticated media GET, server-side type/size limits, attachment text run through `redact()` before model snapshots). There is **no outbound SMS/iMessage path** in this diff. Main risks are **attachment lifecycle/oracle issues**, a **35 MB video limit vs JSON/base64 body cap mismatch**, **quick-action sends accidentally including staged attachments**, and **heavy synchronous video enrichment** on the reply worker.

---

## Findings (by severity)

### High

1. **Staged attachments ride along on quick-chip / `submitChatText` sends**  
   `submitChatText()` always adds `attachments: pendingAttachments.map(...)` to the payload and does **not** clear `pendingAttachments` after send (unlike the main composer submit path). If Jeff attaches files then taps **Status**, **Texts** (on integrate branches), **Start round**, etc., those unrelated commands can be submitted **with the staged media IDs**.  
   - **Where:** `webchat/static/app.js` (`submitChatText`, chip handlers).  
   - **Impact:** Wrong context sent to the model (unintended images/files + cost/latency); possible confusion or leakage of sensitive files into the wrong turn.  
   - **Tests:** None for chip/quick-action + pending attachment interaction.

### Medium

2. **Advertised 35 MB video max is not reachable through the HTTP API**  
   `MAX_VIDEO_BYTES` and `MAX_MEDIA_BODY` are both 35 MB, but upload uses base64 inside JSON. A ~35 MB file encodes to ~47 MB; `body(limit=MAX_MEDIA_BODY)` rejects the request (**413**) before decode. Effective video ceiling is roughly **~26 MB** unless limits are retuned.  
   - **Where:** `webchat/app.py` (`MAX_MEDIA_BODY`), `webchat/chat_media.py` (`MAX_VIDEO_BYTES`), client `MEDIA_LIMITS.video`.  
   - **Impact:** iPhone videos near the documented cap fail unpredictably; docs and UI promises diverge from behavior.  
   - **Tests:** No upload near-limit / 413 regression.

3. **Global media store — no binding to conversation or uploader**  
   `store_media()` writes to a shared `conductor/webchat/uploads/` namespace; `validate_attachment_ids()` only checks that IDs exist. Any authenticated session can attach any known `media_id`. Assistant outbound markers (`<bob-webchat-attachment …>` / `![…](/api/media/…)`) resolve **any** on-disk upload via `load_meta()` with no provenance check.  
   - **Where:** `webchat/chat_media.py`, `webchat/app.py` (`submit`, assistant attachment resolution).  
   - **Impact:** Cross-conversation attachment oracle (single-tenant mitigates, but compromised model reply or guessed ID can surface another upload in chat or to vision).  
   - **Tests:** No cross-conversation / marker-IDOR tests.

4. **File attachments can bypass the message-body secret gate**  
   Text messages still require `redact(text) == text`, but attachment-only sends skip text redaction. File kinds embed up to 12 KB of raw file bytes into the model snapshot (`read_text_file`); images/video go to vision/transcript paths without content redaction.  
   - **Where:** `webchat/app.py` (`submit`), `webchat/chat_media.py` (`enrich_for_model`), `webchat/providers.py` (snapshot uses `redact` on **text** bundle only; vision base64 is not scanned).  
   - **Impact:** Pasting secrets into chat is blocked; uploading `secrets.txt` or a screenshot of credentials is not.  
   - **Tests:** No redaction-on-attachment-content cases.

5. **Video processing runs synchronously on the reply path**  
   `enrich_for_model()` → `describe_video()` can invoke multiple ffmpeg extractions plus optional Whisper (timeouts up to ~120s per clip) inside the provider worker for a single message.  
   - **Where:** `webchat/chat_media.py`, triggered from `providers.prompt()`.  
   - **Impact:** Long “Thinking…” periods, worker slot held, mobile timeouts; partial failure yields under-informed replies without surfacing processing errors to the user.  
   - **Tests:** Only mocked unit test for video enrich; no timeout/failure integration test.

### Low

6. **Client MIME vs server extension classification mismatch**  
   Browser uses `file.type` for limits/kind; server classifies by filename extension only. A mislabeled or empty `file.type` can pass client checks yet fail server-side (or vice versa).  
   - **Where:** `webchat/static/app.js` (`mediaKindFromFile`), `webchat/chat_media.py` (`classify_suffix`).  
   - **Tests:** None.

7. **Assistant attachment markers fail open**  
   Invalid or unknown `media_id` in model output is silently dropped (`continue` on load errors). Jeff may see prose claiming an attachment without a bubble.  
   - **Where:** `webchat/app.py` (post-reply attachment resolution).  
   - **Tests:** Marker stripping only; not end-to-end assistant attachment attachment.

8. **Gemini API key remains in query string for vision calls** (pre-existing pattern extended by vision payload)  
   `services/api.py` still places `GEMINI_API_KEY` in the URL for `generateContent`. Vision parts do not worsen this, but multimodal prompts increase sensitivity of traffic subject to proxy/logs.  
   - **Note:** Not introduced solely by media, but touched in this diff.

### Mobile Safari / UX

| Issue | Severity | Notes |
| --- | --- | --- |
| Remove control on attach chips is **22×22 px** | Medium (UX/a11y) | Below common 44 px touch target; `webchat/static/style.css` `.attach-chip .attach-remove`. |
| Full-file `FileReader` → base64 before upload | Medium | Large videos load entirely in JS memory; risky on iPhone for clips that already fail server limit. |
| Horizontal scroll on attach preview strip | Low | `-webkit-overflow-scrolling: touch` present; acceptable. |
| `required` removed from textarea | Positive | Enables attachment-only sends as designed. |
| HEIC allowed server-side | Low | Depends on ffmpeg/server decode; not validated in tests on real iOS captures. |
| Proof screenshots | Positive | `live_media_proof.py` uses 390×844 viewport; not a substitute for on-device Safari QA. |

---

## Security: texting / send / secrets (this lane)

| Check | Result |
| --- | --- |
| Real SMS/iMessage send without per-draft yes | **N/A** — no texting/send bridge in this diff. |
| API keys/passwords in client or logs | **No new client secret exposure**; uploads served only to authenticated sessions. |
| Model prompt injection via attachments | User-controlled file content reaches model (expected); mitigated only partially by text `redact()`. |
| CSRF / auth on upload & media GET | **Consistent** with existing webchat API (session + CSRF on POST). |

---

## Test coverage gaps

| Area | Present | Missing |
| --- | --- | --- |
| Store/validate/enrich unit | `test_chat_media.py` | Limit edge cases, ffmpeg failure paths |
| HTTP upload + GET | `test_webchat.py` | Near-limit body 413, rejected types, unauthenticated upload (implicit via suite) |
| Vision transport | Partial via `_vision_parts` | `api_call.py` / `split_transport` round-trip test |
| Assistant outbound markers | Marker parse unit | Handler resolves arbitrary `media_id` |
| Frontend attachment UX | Playwright proof | Chip + `submitChatText` attachment leakage |
| Mobile | Screenshot proof only | Touch targets, memory, real HEIC/MOV |

---

## Positive observations

- Attachment-only messages, idempotent `request_id` with attachment equality, and 409 on mismatch are thoughtfully handled in `Chat.submit`.
- Upload files chmod `600`; metadata sidecars match.
- Vision gated to Gemini/MiniMax with explicit transport framing in `api_call.py`.
- Provider rules document attachment markers and discourage inventing `media_id`s.

---

## Commands run (read-only)

- `git diff draft/webbob-clean-0927...HEAD --stat` / full diff
- Source read: `webchat/chat_media.py`, `webchat/app.py`, `webchat/providers.py`, `webchat/static/app.js`, `webchat/api_call.py`, `services/api.py`, tests

**Reviewer did not re-run the full unit suite** (lane doc claims 178 webchat + 111 services passed at commit time).

# Web Bob media review fixes — 2026-09-27

Worktree: `workspaces/wt-webbob-media-0927`

Branch: `draft/webbob-media-0927`, starting at `cfea813`

Existing PR: [bob-brain #7](https://github.com/rupret007/bob-brain/pull/7), **draft**, targeting `draft/webbob-clean-0927`.

The valid media findings in `CURSOR-REVIEW-MEDIA-0927.md` and
`GEMINI-REVIEW-MEDIA-0927.md` are addressed. Reviewed the original
`WEBBOB-MEDIA-0927.md`, iPhone design notes, and historical media/Safari evidence
limitations as context. The two supplied reviewer files were already untracked;
their contents are preserved unchanged.

## Finding dispositions

| Review finding | Resolution and regression evidence |
| --- | --- |
| Cursor 1: quick actions send staged attachments | Quick commands and confirmation cards have a separate request object with no attachments. Composer drafts retain their media/text, including across conversation switches. WebKit/Chromium stage media, tap Status, inspect the actual POST, switch chats, restore the draft, and send it separately. |
| Cursor 2: 35 MB video cap unreachable | Browser uploads raw `File` bodies with progress; no FileReader/base64 memory copy. JSON compatibility has a base64-aware cap. HTTP tests upload a full **35 MiB** through both paths and reject an oversized raw body before reading it. |
| Cursor 3: global store / arbitrary marker IDs | Metadata is bound to a conversation at upload. Submit, GET/HEAD, enrichment, and outbound marker resolution enforce that binding. No orphan lookup or metadata synthesis. Tests cover foreign/missing IDs, corrupt sidecars, symlinks, and foreign outbound markers. This remains a single-owner application: login sessions are devices of the same owner, not separate user accounts. |
| Cursor 4: attachment secret-gate bypass | Uploads reject recognized secrets in complete decoded file bytes and filenames before persistence, including text beyond the prompt excerpt. Model text/PDF/transcript inputs are redacted. Normalized image and video-frame OCR runs locally before remote vision; a detected secret or failed/unavailable scanner withholds visual content. Tests cover text and filename rejection, PDF/transcript redaction, OCR failure/secret detection, and dropping a whole clip when one sampled frame is blocked. |
| Cursor 5 / Gemini 1: excessive video processing and hidden failures | The HTTP submit path already used a reply worker; it remains asynchronous. Preparation now has a shared **20-second** budget across the turn, two concurrent preparations, 3–8 second subprocess caps, one decoder thread, bounded frame dimensions/count/output, cancellation, and process-group cleanup. Missing tools, timeouts, bad codecs and partial failures produce visible notes while preserving readable files. Whisper uses only cached weights. Tests include actual child cancellation and real MOV frame extraction. |
| Cursor 6: MIME / extension mismatch | Client and server use the same extension sets and limits; server also checks signatures/UTF-8. Real browser tests upload a video with empty MIME and a text file with an incorrect image MIME. Unsupported and malformed uploads have HTTP/unit coverage. |
| Cursor 7: outbound markers fail silently | Both XML-style and Markdown attachment markers are stripped and resolved server-side, including invalid forms. Missing/foreign IDs produce an explicit notice. Provider-supplied attachment dictionaries cannot bypass validation. HTTP tests return photos, videos, and files and fetch the resulting originals. |
| Cursor 8: Gemini key in URL | Gemini authentication uses `x-goog-api-key`, never a query parameter. The stubbed service transport test asserts header auth and inline image data. |
| Cursor mobile / Gemini 4: tiny remove target | Remove buttons have a real 44×44 CSS-pixel box. Download controls are at least 44 pixels high. Browser tests measure the remove target and exercise reduced-height and landscape layouts. The suggested 26-pixel patch would not meet this requirement and was not used. |
| Cursor mobile: FileReader memory / previews / HEIC | Raw uploads avoid base64 expansion on iPhone. Same-origin previews pass the actual CSP without blob exceptions. HEIC previews use the native Mac decoder and bounded normalization; original HEIC downloads remain available. Both browsers decode a locally generated HEIC preview. |
| Gemini 2: delimiter transport corruption | Provider stdin is one validated JSON envelope containing prompt and vision. Tests preserve the former delimiter, Unicode, and quotes, reject invalid envelopes, and run a vision round-trip through a child process with a stubbed API module. |
| Gemini 3: missing error coverage | Added store/limit/signature/ownership, process timeout/nonzero/missing-tool/cancellation, OCR, PDF, malformed marker, HTTP and browser regressions. Details below. |
| Gemini 5: blob glob fallback | Removed. Only a valid owned sidecar and matching regular blob resolve. Orphans, invalid suffixes and symlinks fail closed. |
| Gemini summary: removed `chat_intent` tests | Not a change in the reviewed `cfea813` media commit. Existing natural dispatch, follow-up and draft-rule regression tests remain and pass; no unrelated dispatch rewrite was made. |

## Additional defects found while validating

- Vision parts were stored on the shared provider instance. They now live in
  thread-local call state. A synchronized three-conversation test proves that two
  image turns and one text turn cannot exchange or clear each other's payloads.
- Video responses lacked Range/HEAD handling. Added streamed single-byte-range
  serving, 206/416 responses, correct lengths, original download filenames and
  `playsinline`. WebKit actually plays and seeks a locally generated MOV; Chromium
  plays/seeks WebM. Unsupported codecs retain a clear download fallback.
- The CSP blocked the app's manifest. Added `manifest-src 'self'`; browser tests
  run with the real CSP and assert no violations.
- The configured MiniMax M2.7 transport claimed vision capability it does not
  provide. Auto photo/video turns prefer Gemini. Text-only fallbacks receive local
  extracted text and disclose that they did not see images/frames.
- Uploading and sending could race with conversation changes. Controls now guard
  in-flight uploads; successful sends clear only submitted attachments. A lost
  response test retries the exact request ID without duplicating the turn.
- PDF files previously entered context as raw binary. Added bounded text
  extraction using `pdftotext` or native macOS PDFKit, plus a real PDF redaction
  test. Scanned/locked/unreadable documents get an honest explanation.

The relevant provider/browser contracts were checked against primary documentation:
[Google image inputs and header authentication](https://ai.google.dev/gemini-api/docs/image-understanding),
[Apple inline media playback](https://developer.apple.com/documentation/webkit/delivering-video-content-for-safari),
and [MiniMax model-specific multimodal support](https://platform.minimax.io/docs/api-reference/text-openai-api).

## Verification

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **203 passed**, including the existing dispatch/failover/security suite |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **113 passed** |
| `python3 webchat/media_browser_test.py --screenshots reviews` | **WebKit + Chromium passed** |
| `python3 bootstrap.py check` | **syntax: PASS** |
| `node --check webchat/static/app.js` | **PASS** |
| `node --check webchat/test_media_browser.cjs` | **PASS** |
| `node --test webchat/test_quiet_hours_js.mjs` | **PASS** |
| `git diff --check` | **PASS** |

Browser coverage includes PNG, MOV/WebM, text and PDF uploads; attachment-only
sending; assistant echoes; authenticated original downloads; actual video
playback/seeking; HEIC previews; quick action isolation; draft switching; a lost
send response with idempotent retry; failed uploads; upload progress and disabled
controls; touch targets; CSP; browser reload; and 390×844, 390×500, 844×390 layouts.
Fixtures and providers are deterministic. Tests do not contact any model service.
The service suite's restart log lines come from its mocked watchdog test, not
service-control commands against this machine.

Screenshots from the isolated browser fixture:
[WebKit](MEDIA-FIXED-0927-webkit.png) · [Chromium](MEDIA-FIXED-0927-chromium.png).

## Limits and rollout status

- **Not deployed.** No live service was started, stopped, or restarted. No texts,
  emails, model calls, Grok/xAI requests, merges, undrafts, or force pushes were
  made. No existing password was printed. Tests use temporary roots and ephemeral
  loopback listeners, generated fixture credentials, and stub providers.
- WebKit with an iPhone device profile is automated browser evidence, **not a
  physical iPhone Safari/camera-roll/keyboard or low-memory device sign-off**.
  Chromium's bundled codec support differs, so its playback fixture is WebM.
- OCR detects recognized secrets; it cannot guarantee detection of every
  credential, handwriting, or text obscured by image quality. Only checked
  normalized frames go to remote vision. Do not interpret this as comprehensive
  screenshot data-loss prevention.
- Video understanding is sampled, not exhaustive: at most four frames from the
  first 120 seconds, optional audio from the first 30 seconds. PDF understanding
  uses extractable text from at most 20 pages. Failures are visible. Actual
  provider answer quality and live multimodal quota/failover were not exercised.
- Unbound metadata from the initial draft fails closed; those files need to be
  reattached after any future rollout. Submitted attachments persist with chat
  history; unsent composer drafts are held only for the current page session.

These changes close the reviewed media reliability gaps toward Bob parity; they
do not claim a live or on-device quality win over Bob without that separate proof.

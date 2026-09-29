# Web Bob media attachments — 2026-09-27

**Branch:** `draft/webbob-media-0927`
**Base PR target:** `draft/webbob-clean-0927` (DRAFT; never `main`)
**Parity context:** Read `conductor/reviews/WEBBOB-PARITY-0927.md` (Bob-the-Bot audit) before this lane; media was not in the ranked plan but closes a major phone/desktop gap vs. everyday Bob chat.

## Summary

Web Bob now supports **photos, videos, and files** from the composer **+** button (camera roll / files on phone, desktop picker on Mac), with **preview chips**, **server-side limits**, **model vision** (Gemini/MiniMax multimodal + text fallbacks for Codex/Cursor/Claude), **video understanding** via **ffmpeg frame sampling** and **optional Whisper transcript**, and **outbound attachments** when Bob replies with `<bob-webchat-attachment … />` or `![caption](/api/media/…)`.

No live `:8787` service was restarted or deployed. Proof used an **isolated ephemeral listener** and **StubProviders** (no Grok, no live model spend for the screenshot pass).

## Limits

| Kind | Max size | Max per message |
| --- | ---: | ---: |
| Image | 12 MB | 6 total attachments |
| Video | 35 MB | (combined) |
| Other files (pdf, txt, md, csv, json, log) | 8 MB | |

Stored under `conductor/webchat/uploads/` with `media_id` + `.meta.json` sidecar (mode `600`).

## API

- `POST /api/media/upload` — `{ filename, data_base64 }` → attachment metadata + `/api/media/{id}` URL
- `GET /api/media/{id}` — authenticated binary serve
- `POST /api/messages` — optional `attachments: ["media_id", …]`; text optional when attachments present

## UI

- **+** in composer opens multi-select (`image/*`, `video/*`, common docs)
- Preview strip above composer; remove per chip
- Chat bubbles render image/video/file links for user and assistant messages

## Model path

- `chat_media.enrich_for_model()` builds text + vision parts (resize large images for prompt budget)
- `providers.prompt()` adds `chat_attachments (current turn)` snapshot
- `api_call.py` sends vision JSON to Gemini/MiniMax when supported (`services.api.model_call(..., vision=…)`)

## Tests added/updated

| Area | File |
| --- | --- |
| Media store/validate/video enrich | `webchat/test_chat_media.py` (5 tests) |
| HTTP upload, message, attachment-only | `webchat/test_webchat.py` |
| Prompt vision parts | `webchat/test_webchat.py` |

## Verification

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s webchat -p 'test_*.py'` | **178 passed** |
| `python3 -m unittest discover -s services -p 'test_*.py'` | **111 passed** |
| `node --test webchat/test_quiet_hours_js.mjs` | **1 passed** |
| `python3 bootstrap.py check` | **syntax: PASS** |
| `python3 webchat/live_media_proof.py --output reviews/WEBBOB-MEDIA-0927.evidence.json --screenshots reviews` | **PASS** |

## Screenshots (isolated server)

| File | What |
| --- | --- |
| [WEBBOB-MEDIA-0927-login.png](WEBBOB-MEDIA-0927-login.png) | Mobile login |
| [WEBBOB-MEDIA-0927-chat.png](WEBBOB-MEDIA-0927-chat.png) | User bubble with inline image |
| [WEBBOB-MEDIA-0927-attach-preview.png](WEBBOB-MEDIA-0927-attach-preview.png) | Composer + preview chip before send |

Evidence JSON: [WEBBOB-MEDIA-0927.evidence.json](WEBBOB-MEDIA-0927.evidence.json)

Reproduce proof:

```sh
python3 webchat/live_media_proof.py \
  --output reviews/WEBBOB-MEDIA-0927.evidence.json \
  --screenshots reviews
```

Requires Playwright under `conductor/webchat/node_modules` (walks parent dirs from the worktree).

## Changed files

- `webchat/chat_media.py` (new)
- `webchat/app.py`, `webchat/providers.py`, `webchat/api_call.py`
- `webchat/static/index.html`, `webchat/static/app.js`, `webchat/static/style.css`
- `services/api.py` (optional `vision` on `model_call`)
- `webchat/test_chat_media.py`, `webchat/test_webchat.py`
- `webchat/live_media_proof.py`, `webchat/media_proof_capture.cjs` (new)
- `reviews/WEBBOB-MEDIA-0927.md`, evidence + screenshots

## Remaining risks

- **Whisper** transcript is best-effort (only when `whisper`/`whisper-cli` is on PATH); silent clips still get frame samples.
- **HEIC** and exotic codecs depend on ffmpeg on the mini.
- **Very large** phone videos may hit upload time on slow networks before server limits apply.
- **Codex/Cursor/Claude** paths get attachment **text + frame descriptions**, not native vision APIs (by design in this lane).
- Outbound attachments require the model to use the documented markers with a **real** `media_id` (server validates on save).

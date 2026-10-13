#!/usr/bin/env python3
"""Private conversation attachments and bounded, local media preparation."""
from __future__ import annotations

import base64
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

UPLOADS = Path("conductor/webchat/uploads")
MEDIA_ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_ATTACHMENTS_PER_MESSAGE = 6
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_VIDEO_BYTES = 35 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 50 * 1024 * 1024
MAX_PROMPT_IMAGE_BYTES = 420_000
MEMO_TRANSCRIBE_MAX_S = 30
WHISPER_MODEL = "tiny"
WHISPER_TRANSCRIBE_TIMEOUT_S = 8
TRANSCRIPTION_UNAVAILABLE = "Transcription unavailable: cached model missing"
UNSUPPORTED_AUDIO_MESSAGE = "Unsupported audio format. Accepted: m4a, mp3, wav."
MAX_VIDEO_FRAMES = 4
MAX_VIDEO_DURATION_S = 120
MEDIA_PREP_SECONDS = 20
PROCESS_SLOTS = threading.BoundedSemaphore(2)
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
ALLOWED_VIDEO = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}
ALLOWED_FILE = {".pdf", ".txt", ".md", ".csv", ".json", ".log"}
ALLOWED_AUDIO = {".m4a", ".mp3", ".wav"}
REJECTED_AUDIO = {".flac", ".ogg", ".aac", ".opus", ".wma", ".aiff", ".aif"}
ATTACHMENT_TAG = re.compile(r'<bob-webchat-attachment\b[^>]*(?:>|$)', re.I)
MEDIA_LINK = re.compile(r'!?\[[^\]]*\]\(/api/media/([^\s)]+)\)', re.I)


def _upload_dir(root: Path) -> Path:
    path = root / UPLOADS
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def _meta_path(root: Path, media_id: str) -> Path:
    return _upload_dir(root) / (media_id + ".meta.json")


def classify_suffix(suffix: str) -> str:
    s = suffix.lower() if suffix.startswith(".") else "." + suffix.lower()
    if s in ALLOWED_IMAGE:
        return "image"
    if s in ALLOWED_VIDEO:
        return "video"
    if s in ALLOWED_AUDIO:
        return "audio"
    if s in ALLOWED_FILE:
        return "file"
    if s in REJECTED_AUDIO:
        raise ValueError(UNSUPPORTED_AUDIO_MESSAGE)
    raise ValueError("Unsupported file type for chat.")


def media_limit(filename: str) -> int:
    if not isinstance(filename, str) or not filename or len(filename) > 240 or re.search(r'[\x00-\x1f\x7f]', filename):
        raise ValueError("Invalid attachment filename.")
    name = filename.strip()
    if not name or name != filename:
        raise ValueError("Invalid attachment filename.")
    kind = classify_suffix(Path(name).suffix)
    return {"image": MAX_IMAGE_BYTES, "video": MAX_VIDEO_BYTES, "audio": MAX_AUDIO_BYTES, "file": MAX_FILE_BYTES}[kind]


def _check_signature(data: bytes, suffix: str):
    """Do not feed disguised playlists/HTML/arbitrary data to media decoders."""
    if suffix in {".jpg", ".jpeg"}:
        valid = data.startswith(b'\xff\xd8\xff')
    elif suffix == ".png":
        valid = data.startswith(b'\x89PNG\r\n\x1a\n')
    elif suffix == ".gif":
        valid = data.startswith((b'GIF87a', b'GIF89a'))
    elif suffix == ".webp":
        valid = len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP'
    elif suffix in {".heic", ".heif", ".mp4", ".mov", ".m4v", ".m4a"}:
        valid = len(data) >= 8 and data[4:8] in (b'ftyp', b'moov', b'mdat', b'wide')
    elif suffix == ".mp3":
        valid = data.startswith(b'ID3') or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)
    elif suffix == ".wav":
        valid = len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WAVE'
    elif suffix in {".mkv", ".webm"}:
        valid = data.startswith(b'\x1aE\xdf\xa3')
    elif suffix == ".pdf":
        valid = data.startswith(b'%PDF-')
    else:
        try:
            data.decode("utf-8")
            valid = b'\x00' not in data
        except UnicodeError:
            valid = False
    if not valid:
        raise ValueError("File content does not match its type, or is not UTF-8 text.")


def _reject_embedded_secrets(data: bytes, name: str, redact) -> None:
    """Scan filename and raw bytes so secrets embedded in binary cannot slip past redact."""
    if redact(name) != name:
        raise ValueError("This attachment appears to contain a secret. Remove it before uploading.")
    for view in (data.decode("latin-1"), data.decode("utf-8", errors="replace")):
        if redact(view) != view:
            raise ValueError("This attachment appears to contain a secret. Remove it before uploading.")


def store_media(root: Path, data: bytes, filename: str, *, conversation_id: str, redact) -> dict:
    from providers import UUID
    if not isinstance(conversation_id, str) or not UUID.fullmatch(conversation_id):
        raise ValueError("A conversation is required for attachments.")
    limit = media_limit(filename)
    name = Path(filename.replace('\\', '/')).name
    suffix = Path(name).suffix.lower()
    kind = classify_suffix(suffix)
    if len(data) > limit:
        raise ValueError(f"File too large ({limit // (1024 * 1024)}MB max for {kind}).")
    if not data:
        raise ValueError("Empty file.")
    _check_signature(data, suffix)
    # Scan the complete upload, not just the eventual prompt excerpt. No secrets
    # in a text file, filename, or embedded metadata are persisted through HTTP.
    if redact is None:
        raise ValueError("Secret scanning requires a redact callable.")
    _reject_embedded_secrets(data, name, redact)
    if kind == "image":
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / ("upload" + suffix)
            probe.write_bytes(data)
            blob, _ = prompt_image_bytes(probe, MediaBudget(seconds=5))
            scan_image(blob, MediaBudget(seconds=5), redact)
    token = secrets.token_hex(16)
    path = _upload_dir(root) / (token + suffix)
    meta = {"media_id": token, "conversation_id": conversation_id, "filename": name,
            "suffix": suffix, "kind": kind, "bytes": len(data), "path": str(path.relative_to(root))}
    meta_path = _meta_path(root, token)
    try:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as out:
            out.write(data)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    try:
        with os.fdopen(os.open(meta_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as out:
            json.dump(meta, out)
    except Exception:
        path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        raise
    if kind == "audio":
        meta["duration_s"] = _probe_duration(path, MediaBudget(seconds=5))
    return meta


def load_meta(root: Path, media_id: str, *, conversation_id: str) -> dict:
    # A blob is addressable only through a valid, owned sidecar. Never glob or
    # manufacture metadata for an orphan; legacy unbound uploads fail closed.
    if not isinstance(media_id, str) or not MEDIA_ID_RE.fullmatch(media_id):
        raise FileNotFoundError("Attachment not found.")
    try:
        sidecar = _meta_path(root, media_id)
        if sidecar.is_symlink():
            raise ValueError()
        meta = json.loads(sidecar.read_text())
        suffix = meta["suffix"]
        allowed = ALLOWED_IMAGE | ALLOWED_VIDEO | ALLOWED_FILE | ALLOWED_AUDIO
        if (not conversation_id or meta["conversation_id"] != conversation_id
                or meta["media_id"] != media_id or suffix not in allowed
                or meta["kind"] != classify_suffix(suffix)):
            raise ValueError()
        path = _upload_dir(root) / (media_id + suffix)
        if path.is_symlink() or not path.is_file():
            raise ValueError()
        meta["path"] = str(path.relative_to(root))
        return meta
    except (OSError, ValueError, TypeError, KeyError):
        raise FileNotFoundError("Attachment not found.") from None


def resolve_media(root: Path, media_id: str, *, conversation_id: str) -> Path:
    return root / load_meta(root, media_id, conversation_id=conversation_id)["path"]


def validate_attachment_ids(root: Path, ids: list, *, conversation_id: str) -> list[dict]:
    if not isinstance(ids, list):
        raise ValueError("attachments must be a list.")
    if len(ids) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise ValueError(f"At most {MAX_ATTACHMENTS_PER_MESSAGE} attachments per message.")
    out, seen = [], set()
    for item in ids:
        mid = item if isinstance(item, str) else (item.get("media_id") if isinstance(item, dict) else None)
        if not isinstance(mid, str) or not MEDIA_ID_RE.fullmatch(mid):
            raise ValueError("Invalid attachment id.")
        if mid not in seen:
            seen.add(mid)
            out.append(load_meta(root, mid, conversation_id=conversation_id))
    return out


class MediaBudget:
    def __init__(self, cancel=None, seconds=MEDIA_PREP_SECONDS):
        self.cancel = cancel or threading.Event()
        self.deadline = time.monotonic() + seconds

    def run(self, args, timeout=5):
        from providers import Cancelled, ProviderError, run
        if self.cancel.is_set():
            raise Cancelled("Reply stopped.")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Media preparation timed out; try a smaller attachment.")
        try:
            code, out, _ = run(args, cwd=Path(tempfile.gettempdir()),
                               env=dict(os.environ, OMP_THREAD_LIMIT="1", OMP_NUM_THREADS="1"),
                               cancel=self.cancel, timeout=min(timeout, remaining))
        except Cancelled:
            raise
        except (ProviderError, OSError, subprocess.TimeoutExpired):
            raise ValueError("Media preparation failed or timed out; try a smaller attachment.") from None
        if code:
            raise ValueError("Could not decode or read this attachment.")
        return out


def _run_ffmpeg(args: list[str], budget=None):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("Media preview unavailable: ffmpeg is not installed.")
    return (budget or MediaBudget()).run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-threads", "1", "-filter_threads", "1", "-max_alloc", "67108864", "-protocol_whitelist", "file,pipe", *args])


def _probe_duration(path: Path, budget=None) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = (budget or MediaBudget()).run([ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe",
            "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], timeout=3)
        value = float(out.strip())
        return value if math.isfinite(value) and value > 0 else None
    except ValueError:
        return None


def prompt_image_bytes(path: Path, budget=None) -> tuple[bytes, str]:
    # Normalize even small images: strip embedded metadata and turn HEIC into a
    # broadly supported image. sips is the native decoder on the Mac mini.
    budget = budget or MediaBudget()
    with tempfile.TemporaryDirectory() as tmp:
        source = path
        if path.suffix.lower() in {".heic", ".heif"} and shutil.which("sips"):
            source = Path(tmp) / "decoded.png"
            budget.run(["sips", "-s", "format", "png", str(path), "--out", str(source)])
        for quality, scale in ((6, 1280), (4, 960), (2, 640), (1, 480)):
            out = Path(tmp) / f"image_q{quality}.jpg"
            _run_ffmpeg(["-i", str(source), "-frames:v", "1", "-vf",
                         f"scale='min({scale},iw)':'min({scale},ih)':force_original_aspect_ratio=decrease",
                         "-threads", "1", "-map_metadata", "-1", "-q:v", str(quality), str(out)], budget)
            if out.is_file() and 0 < out.stat().st_size <= MAX_PROMPT_IMAGE_BYTES:
                return out.read_bytes(), "jpeg"
        raise ValueError(
            f"Image is too complex to reduce below {MAX_PROMPT_IMAGE_BYTES // 1024}KB. "
            "Try a smaller or simpler image.")


def extract_video_frames(path: Path, duration: float | None, budget=None) -> list[dict]:
    budget = budget or MediaBudget()
    dur = min(duration or 30.0, MAX_VIDEO_DURATION_S)
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for idx in range(MAX_VIDEO_FRAMES):
            # Stay before EOF, including sub-second phone clips.
            at = round(dur * idx / MAX_VIDEO_FRAMES, 3)
            out = Path(tmp) / f"frame_{idx}.jpg"
            try:
                _run_ffmpeg(["-ss", str(at), "-i", str(path), "-frames:v", "1", "-vf",
                    "scale='min(1280,iw)':'min(1280,ih)':force_original_aspect_ratio=decrease", "-threads", "1",
                    "-map_metadata", "-1", "-q:v", "6", str(out)], budget)
            except ValueError:
                continue
            if out.is_file() and 0 < out.stat().st_size <= MAX_PROMPT_IMAGE_BYTES:
                frames.append({"time_s": at, "mime": "image/jpeg", "data_base64": base64.b64encode(out.read_bytes()).decode()})
    return frames


def _whisper_cached() -> bool:
    return bool(shutil.which("whisper")) and (Path.home() / ".cache/whisper" / f"{WHISPER_MODEL}.pt").is_file()


def _format_duration(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds) or seconds < 0:
        return "0:00"
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def memo_chip_label(duration_s: float | None = None, *, transcribed: bool = False) -> str:
    parts = ["Voice memo"]
    if duration_s is not None and math.isfinite(duration_s) and duration_s > 0:
        parts.append(_format_duration(duration_s))
    if transcribed:
        parts.append("transcribed locally")
    return " · ".join(parts)


def memo_coverage_label(full_duration_s: float | None, transcribed_s: float, truncated: bool) -> str:
    if truncated and full_duration_s is not None:
        return (f"Transcribed 0:00–{_format_duration(transcribed_s)} of "
                f"{_format_duration(full_duration_s)} (truncated)")
    if transcribed_s > 0:
        return f"Transcribed 0:00–{_format_duration(transcribed_s)}"
    return "Transcription coverage not available"


def _memo_no_transcription_meta(full_duration: float | None) -> dict:
    return {"full_duration_s": full_duration, "transcribed_duration_s": 0, "truncated": False,
            "coverage_label": "Transcription coverage not available"}


def _memo_success_transcription_meta(full_duration: float | None) -> dict:
    if full_duration is not None and math.isfinite(full_duration) and full_duration > 0:
        transcribed_s = min(MEMO_TRANSCRIBE_MAX_S, full_duration)
    else:
        transcribed_s = float(MEMO_TRANSCRIBE_MAX_S)
    truncated = full_duration is not None and full_duration > MEMO_TRANSCRIBE_MAX_S
    return {"full_duration_s": full_duration, "transcribed_duration_s": transcribed_s, "truncated": truncated,
            "coverage_label": memo_coverage_label(full_duration, transcribed_s, truncated)}


def transcribe_voice_memo(path: Path, budget=None) -> dict:
    """Local ffmpeg + cached Whisper only. Never downloads model weights."""
    budget = budget or MediaBudget()
    full_duration = _probe_duration(path, budget)
    common = {"source": "local-cache", "model": f"{WHISPER_MODEL}.pt"}
    if not _whisper_cached():
        return {**common, **_memo_no_transcription_meta(full_duration),
                "status": "unavailable", "text": TRANSCRIPTION_UNAVAILABLE}
    whisper = shutil.which("whisper")
    timeout = min(WHISPER_TRANSCRIBE_TIMEOUT_S, max(1, budget.deadline - time.monotonic()))
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        try:
            _run_ffmpeg(["-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                         "-t", str(MEMO_TRANSCRIBE_MAX_S), str(wav)], budget)
            budget.run([whisper, str(wav), "--model", WHISPER_MODEL, "--output_format", "txt", "--output_dir", tmp,
                        "--language", "en", "--threads", "1", "--fp16", "False"], timeout=timeout)
            text = (Path(tmp) / "audio.txt").read_text(errors="replace")[:8000].strip()
        except ValueError as exc:
            reason = str(exc).lower()
            if "timed out" in reason:
                return {**common, **_memo_no_transcription_meta(full_duration), "status": "timeout",
                        "text": f"Transcription timed out after {int(timeout)} s. Memo not transcribed."}
            return {**common, **_memo_no_transcription_meta(full_duration), "status": "failed", "text": ""}
        except OSError:
            return {**common, **_memo_no_transcription_meta(full_duration), "status": "failed", "text": ""}
    if not text:
        return {**common, **_memo_no_transcription_meta(full_duration), "status": "empty", "text": ""}
    return {**common, **_memo_success_transcription_meta(full_duration), "status": "ok", "text": text}


def extract_audio_transcript(path: Path, budget=None) -> str:
    result = transcribe_voice_memo(path, budget)
    return result["text"] if result.get("status") == "ok" else ""


def read_text_file(path: Path, limit=MAX_FILE_BYTES, budget=None) -> str:
    if path.suffix == ".pdf":
        binary = shutil.which("pdftotext")
        budget = budget or MediaBudget()
        if binary:
            text = budget.run([binary, "-f", "1", "-l", "20", str(path), "-"])
        elif sys.platform == "darwin" and shutil.which("osascript"):
            text = budget.run(["osascript", "-l", "JavaScript", str(Path(__file__).with_name("pdf_text.js")), str(path)])
        else:
            raise ValueError("PDF text extraction is unavailable; download the PDF or attach a text export.")
        if not text.strip():
            raise ValueError("This PDF has no readable text; attach images of the scanned pages or a text export.")
        return text[:limit]
    with path.open("r", encoding="utf-8") as src:
        return src.read(limit)


def scan_image(blob: bytes, budget: MediaBudget, redact) -> str:
    """Local OCR before any remote vision. Fail closed on scanner failure."""
    ocr = shutil.which("tesseract")
    if not ocr:
        raise ValueError("Image analysis unavailable: the local text safety check is not installed.")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scan.jpg"
        path.write_bytes(blob)
        text = (budget.run([ocr, str(path), "stdout", "--psm", "11"], timeout=3) or "").strip()
    if not text:
        return ""
    if redact(text) != text or redact(re.sub(r'\s+', '', text)) != re.sub(r'\s+', '', text):
        raise ValueError("Image analysis blocked: visible text appears to contain a secret. Remove it and reattach.")
    return text[:4000].strip()


def enrich_for_model(root: Path, metas: list[dict], *, redact, cancel=None) -> dict:
    """One shared deadline and at most two preparations, on reply workers only."""
    text_blocks, vision, warnings = [], [], []
    acquired = PROCESS_SLOTS.acquire(timeout=0.1)
    if not acquired:
        return {"text": "Media preparation busy. No attachment content was read.", "vision": [],
                "warnings": ["Attachments could not be analyzed because media processing is busy. Please retry."]}
    budget = MediaBudget(cancel)
    try:
        for meta in metas:
            label = redact(meta.get("filename") or "Attachment")
            label += f" [media_id={meta['media_id']}]"
            try:
                path = resolve_media(root, meta["media_id"], conversation_id=meta["conversation_id"])
                if meta["kind"] == "image":
                    blob, fmt = prompt_image_bytes(path, budget)
                    ocr = scan_image(blob, budget, redact)
                    text_blocks.append(f"Image attachment {label}. Local text: {ocr or '(no text detected)'}")
                    vision.append({"mime": f"image/{fmt}", "data_base64": base64.b64encode(blob).decode(), "caption": label})
                elif meta["kind"] == "video":
                    duration = _probe_duration(path, budget)
                    frames = extract_video_frames(path, duration, budget)
                    safe_frames, frame_text = [], []
                    for frame in frames:
                        ocr = scan_image(base64.b64decode(frame["data_base64"]), budget, redact)
                        safe_frames.append({**frame, "caption": f"{label} @ {frame['time_s']}s"})
                        if ocr:
                            frame_text.append(ocr)
                    transcript = redact(extract_audio_transcript(path, budget))
                    if not safe_frames:
                        raise ValueError("No video frames could be read; try a shorter MP4 or MOV clip.")
                    vision.extend(safe_frames)
                    text_blocks.append(f"Video attachment {label}. Sampled {len(safe_frames)} frames from the first {MAX_VIDEO_DURATION_S}s maximum.\n"
                                       + "\n".join(frame_text) + "\nAudio transcript (first 30s maximum): " + (transcript or "unavailable"))
                    if not transcript:
                        warnings.append(f"{redact(meta['filename'])}: audio transcript unavailable; analysis uses sampled frames only.")
                elif meta["kind"] == "audio":
                    memo = transcribe_voice_memo(path, budget)
                    chip = memo_chip_label(meta.get("duration_s") or memo.get("full_duration_s"),
                                           transcribed=memo.get("status") == "ok")
                    transcript = redact(memo.get("text") or "")
                    text_blocks.append(
                        f"Voice memo attachment {label} ({chip}).\n"
                        f"{memo.get('coverage_label') or memo_coverage_label(memo.get('full_duration_s'), memo.get('transcribed_duration_s', 0), memo.get('truncated'))}\n"
                        f"Transcript: {transcript or '(empty)'}")
                    if memo.get("status") == "ok":
                        text_blocks[-1] += f"\nTranscription source={memo.get('source')} model={memo.get('model')} coverage_seconds={memo.get('transcribed_duration_s')}"
                        if memo.get("truncated"):
                            coverage = (memo.get("coverage_label")
                                        or memo_coverage_label(memo.get("full_duration_s"),
                                                               memo.get("transcribed_duration_s", 0),
                                                               memo.get("truncated")))
                            warnings.append(f"{redact(meta['filename'])}: {coverage} (first {int(MEMO_TRANSCRIBE_MAX_S)}s only)")
                    elif memo.get("status") == "unavailable":
                        warnings.append(f"{redact(meta['filename'])}: {TRANSCRIPTION_UNAVAILABLE}")
                    elif memo.get("status") == "timeout":
                        warnings.append(f"{redact(meta['filename'])}: {memo.get('text')}")
                    elif memo.get("status") == "empty":
                        warnings.append(f"{redact(meta['filename'])}: no speech detected in the transcribed portion.")
                    elif memo.get("status") == "failed":
                        warnings.append(f"{redact(meta['filename'])}: voice memo could not be transcribed.")
                else:
                    excerpt = redact(read_text_file(path, budget=budget))[:12000]
                    text_blocks.append(f"File attachment {label} (excerpt):\n{excerpt}")
            except (ValueError, OSError) as exc:
                # Never expose decoder stderr or local paths to the chat/model.
                reason = str(exc) if isinstance(exc, ValueError) else "Attachment could not be read."
                warning = f"{redact(meta['filename'])}: {redact(reason)}"
                warnings.append(warning)
                text_blocks.append(warning)
    finally:
        if acquired:
            PROCESS_SLOTS.release()
    return {"text": redact("\n\n".join(text_blocks)), "vision": vision, "warnings": warnings}


def strip_assistant_attachment_markers(content: str) -> tuple[str, list[dict]]:
    attachments = []
    def tag(match):
        mid = re.search(r'media_id=["\x27]([^"\x27]*)["\x27]', match[0], re.I)
        attachments.append({"media_id": mid[1] if mid else ""})
        return ""
    def link(match):
        attachments.append({"media_id": match[1].split('?', 1)[0]})
        return ""
    cleaned = MEDIA_LINK.sub(link, ATTACHMENT_TAG.sub(tag, content))
    return cleaned.strip(), attachments


def requested_attachment_ids(message: dict) -> list[str]:
    """Resolve explicit local returns of unchanged uploads on this user turn.

    This conservative selector is not a file-editing or sending capability.
    It handles standalone directives with a unique target or an explicit set;
    other wording still uses the normal model marker path. Only current upload
    metadata supplies candidates. The caller must revalidate ownership.
    """
    from answer_intent import instructions, requires_execution
    text = message.get('content') or ''
    attachments = message.get('attachments') or []
    if (message.get('role') != 'user' or not isinstance(text, str) or len(text) > 12000 or
            not isinstance(attachments, list) or len(attachments) > MAX_ATTACHMENTS_PER_MESSAGE or
            text.count('```') % 2 or re.search(r'uploadselection\d+asset', text, re.I)):
        return []
    owned = [a for a in attachments if isinstance(a, dict) and
             isinstance(a.get('media_id'), str) and MEDIA_ID_RE.fullmatch(a['media_id'])]
    if not owned:
        return []
    # Protect exact uploaded filenames, including quoted names, while removing
    # quoted instructions. A quoted whole command remains quoted and is removed.
    named = {}
    for item in owned:
        name = item.get('filename')
        if isinstance(name, str) and name:
            named.setdefault(name.casefold(), []).append(item)
    selectors = {}
    for index, (name, items) in enumerate(sorted(named.items(), key=lambda pair: -len(pair[0]))):
        token = 'uploadselection' + str(index) + 'asset'
        for left, right in (('"', '"'), ("'", "'"), ('`', '`'), ('“', '”'), ('‘', '’')):
            text = re.sub(re.escape(left + name + right), token, text, flags=re.I)
        # Bare names must look like filenames, not arbitrary instruction text.
        # Names with spaces or no extension remain selectable when quoted.
        if re.fullmatch(r'[\w-]+(?:[.][\w-]+)+', name):
            text = re.sub(r'(?<!\w)' + re.escape(name) + r'(?!\w)', token, text, flags=re.I)
        selectors[token] = items
    unquoted = instructions(text)
    # Apart from protected filenames, quoted material can qualify the request
    # as well as contain examples. Do not silently drop it to grant a return.
    if unquoted != text:
        return []
    text = unquoted.lower()
    if text.count('"') % 2 or text.count('“') != text.count('”') or text.count('‘') != text.count('’'):
        return []
    # Never substitute the original for an edited result, infer a condition's
    # truth, adopt reported/example instructions, or satisfy an external send.
    excluded = (r"\b(?:not|never|no|without|don['’]?t|can['’]?t|cannot|cancel|stop|ignore|disregard|instead|"
                r"nevermind|leave|if|unless|until|before|after|when|once|pending|while|with|by|"
                r"example|hypothetical\w*|suppose|imagine|instructions?|tutorial|meaning)\b|\bhow to\b")
    if re.search(excluded, text) or requires_execution(text) or re.search(r'\bnever\s+mind\b', text):
        return []
    pattern = (r'(?:(?:can|could|would|will) you\s+)?(?:please\s+)?'
               r'(?P<verb>echo|return|attach|re-?attach|send back|send|show)\s+'
               r'(?P<me>me\s+)?(?:(?P<count>all(?: of)?|both)\s+)?'
               r'(?:(?:the|this|these|that|those|my|our|attached|uploaded|original|existing|same)\s+)*'
               r'(?P<target>images?|photos?|pictures?|videos?|audios?|memos?|files?|attachments?|uploadselection\d+asset)'
               r'(?P<suffix>(?:\s+(?:back|again|here|to me|in (?:this|your) (?:chat|reply)|as (?:an? )?attachments?))*)')
    # Every companion clause must be classified. Skipping unknown clauses
    # would turn reported text or an unfamiliar edit verb into permission to
    # return the unmodified original. The limited read context permits the
    # ordinary image + text/PDF question without granting transformation scope.
    # Deliberately a noun vocabulary, not an arbitrary tail after a read verb:
    # new edit verbs and unparsed conjunctions cannot hide inside read context.
    noun = (r'(?:the|this|these|that|those|my|our|its|their|it|them|all|both|each|'
            r'attached|uploaded|existing|original|dominant|main|primary|'
            r'colou?rs?|contents?|texts?|tokens?|values?|images?|photos?|pictures?|'
            r'videos?|files?|attachments?|documents?|pdfs?|dimensions?|sizes?|'
            r'uploadselection\d+asset)')
    nominal = noun + r'(?:\s+' + noun + r')*'
    # "In PDF" may specify an output format. Read context accepts only an
    # explicit input relation; "in" additionally needs a definite reference.
    source = (r'\s+(?:(?:of|from|on)\s+|in\s+(?:the|this|these|that|those|my|our|attached|uploaded)\s+)'
              + nominal)
    read_prefix = r'(?:(?:can|could|would|will) you\s+)?(?:please\s+)?'
    analysis = (read_prefix + r'(?:describe|identify|read|summari[sz]e|compare|analy[sz]e|explain)\s+'
                + nominal + r'(?:' + source + r')*')
    # "Give the token value" requests a readout; "give the image in PDF"
    # requests a deliverable and must not silently return the original PNG.
    readout = (read_prefix + r'give(?: me)?\s+(?:(?:the|this|these|that|those|its|their|dominant|main|primary)\s+)*'
               r'(?:colou?rs?|tokens?(?:\s+values?)?|values?|dimensions?|sizes?)(?:' + source + r')*')
    noun_continuation = r'(?:the\s+)?(?:attached\s+|uploaded\s+)?(?:pdf|text file|image|photo|picture|video|audio|memo|document|uploadselection\d+asset)s?'
    def current_sources(clause):
        for words, kind in ((r'images?|photos?|pictures?', 'image'), (r'videos?', 'video'), (r'audios?|memos?', 'audio')):
            if re.search(r'\b(?:' + words + r')\b', clause) and not any(a.get('kind') == kind for a in owned):
                return False
        if re.search(r'\bpdfs?\b', clause) and not any(
                str(a.get('filename', '')).lower().endswith('.pdf') for a in owned):
            return False
        return True
    selected, read_context = [], False
    for clause in re.split(r'[.!?;,\n&]+|\b(?:and|then|also|plus|as well as)\b', text):
        clause = clause.strip()
        if not clause:
            continue
        match = re.fullmatch(pattern, clause.strip())
        if not match:
            if (re.fullmatch(analysis, clause) or re.fullmatch(readout, clause)) and current_sources(clause):
                read_context = True
                continue
            if read_context and re.fullmatch(noun_continuation, clause) and current_sources(clause):
                continue
            return []
        read_context = False
        if match['verb'] in ('send', 'show') and not (match['me'] or match['suffix']):
            return []
        target = match['target']
        kind = ('image' if target.rstrip('s') in ('image', 'photo', 'picture')
                else 'video' if target.rstrip('s') == 'video'
                else 'audio' if target.rstrip('s') in ('audio', 'memo') else None)
        options = selectors.get(target, [a for a in owned if kind is None or a.get('kind') == kind])
        plural = target.endswith('s') or match['count'] is not None
        if not options or (match['count'] == 'both' and len(options) != 2) or (not plural and len(options) != 1):
            return []
        selected.extend(a['media_id'] for a in options)
    return list(dict.fromkeys(selected))


def public_attachment(meta: dict) -> dict:
    from urllib.parse import quote
    url = f"/api/media/{meta['media_id']}?conversation_id={quote(meta['conversation_id'], safe='')}"
    out = {"media_id": meta["media_id"], "filename": meta.get("filename") or meta["media_id"],
           "kind": meta.get("kind", "file"), "url": url, "bytes": meta.get("bytes", 0)}
    if meta.get("kind") == "audio":
        out["memo_label"] = memo_chip_label(meta.get("duration_s"))
    return out

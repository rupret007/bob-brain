#!/usr/bin/env python3
"""Chat attachments: store, serve, and describe images/video/files for Web Bob."""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import struct
import tempfile
from pathlib import Path

UPLOADS = Path("conductor/webchat/uploads")
MEDIA_ID_RE = re.compile(r"^[0-9a-f]{16}$")
MAX_ATTACHMENTS_PER_MESSAGE = 6
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_VIDEO_BYTES = 35 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PROMPT_IMAGE_BYTES = 420_000
MAX_VIDEO_FRAMES = 8
MAX_VIDEO_DURATION_S = 120
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
ALLOWED_VIDEO = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}
ALLOWED_FILE = {".pdf", ".txt", ".md", ".csv", ".json", ".log"}
ATTACHMENT_TAG = re.compile(
    r'<bob-webchat-attachment\s+media_id="([0-9a-f]{16})"(?:\s+label="([^"]*)")?\s*/>',
    re.I,
)
MEDIA_LINK = re.compile(r"!\[[^\]]*\]\(/api/media/([0-9a-f]{16})\)")


def _upload_dir(root: Path) -> Path:
    path = root / UPLOADS
    path.mkdir(parents=True, exist_ok=True)
    return path


def _meta_path(root: Path, media_id: str) -> Path:
    return _upload_dir(root) / (media_id + ".meta.json")


def _find_blob(root: Path, media_id: str) -> Path | None:
    if not MEDIA_ID_RE.fullmatch(media_id):
        return None
    folder = _upload_dir(root)
    meta = _meta_path(root, media_id)
    if meta.exists():
        try:
            suffix = json.loads(meta.read_text()).get("suffix", "")
            if suffix:
                candidate = folder / (media_id + suffix)
                if candidate.is_file():
                    return candidate
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    for path in folder.glob(media_id + ".*"):
        if path.name.endswith(".meta.json"):
            continue
        if path.is_file():
            return path
    return None


def classify_suffix(suffix: str) -> str:
    s = suffix.lower() if suffix.startswith(".") else "." + suffix.lower()
    if s in ALLOWED_IMAGE:
        return "image"
    if s in ALLOWED_VIDEO:
        return "video"
    if s in ALLOWED_FILE:
        return "file"
    raise ValueError("Unsupported file type for chat.")


def store_media(root: Path, data: bytes, filename: str) -> dict:
    name = Path(filename or "upload").name
    suffix = Path(name).suffix.lower() or ""
    kind = classify_suffix(suffix)
    limit = MAX_IMAGE_BYTES if kind == "image" else MAX_VIDEO_BYTES if kind == "video" else MAX_FILE_BYTES
    if len(data) > limit:
        raise ValueError(f"File too large ({limit // (1024 * 1024)}MB max for {kind}).")
    if len(data) < 1:
        raise ValueError("Empty file.")
    token = secrets.token_hex(8)
    path = _upload_dir(root) / (token + suffix)
    path.write_bytes(data)
    os.chmod(path, 0o600)
    meta = {
        "media_id": token,
        "filename": name,
        "suffix": suffix,
        "kind": kind,
        "bytes": len(data),
        "path": str(path.relative_to(root)),
    }
    _meta_path(root, token).write_text(json.dumps(meta, indent=2) + "\n")
    os.chmod(_meta_path(root, token), 0o600)
    meta["url"] = f"/api/media/{token}"
    return meta


def load_meta(root: Path, media_id: str) -> dict:
    path = _find_blob(root, media_id)
    if not path:
        raise FileNotFoundError(media_id)
    meta_file = _meta_path(root, media_id)
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
    else:
        meta = {
            "media_id": media_id,
            "filename": path.name,
            "suffix": path.suffix.lower(),
            "kind": classify_suffix(path.suffix),
            "bytes": path.stat().st_size,
            "path": str(path.relative_to(root)),
        }
    meta["url"] = f"/api/media/{media_id}"
    return meta


def resolve_media(root: Path, media_id: str) -> Path:
    path = _find_blob(root, media_id)
    if not path:
        raise FileNotFoundError(media_id)
    return path


def validate_attachment_ids(root: Path, ids: list) -> list[dict]:
    if not isinstance(ids, list):
        raise ValueError("attachments must be a list.")
    if len(ids) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise ValueError(f"At most {MAX_ATTACHMENTS_PER_MESSAGE} attachments per message.")
    out = []
    seen = set()
    for item in ids:
        mid = item if isinstance(item, str) else (item.get("media_id") if isinstance(item, dict) else None)
        if not isinstance(mid, str) or not MEDIA_ID_RE.fullmatch(mid):
            raise ValueError("Invalid attachment id.")
        if mid in seen:
            continue
        seen.add(mid)
        out.append(load_meta(root, mid))
    return out


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg"))


def _run_ffmpeg(args: list[str], timeout: int = 45) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _probe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def _image_size(data: bytes) -> tuple[int, int] | None:
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i < len(data) - 8:
            i += 1
            marker = data[i]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h = struct.unpack(">H", data[i + 3 : i + 5])[0]
                w = struct.unpack(">H", data[i + 5 : i + 7])[0]
                return w, h
            length = struct.unpack(">H", data[i + 1 : i + 3])[0]
            i += length
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    return None


def prompt_image_bytes(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    if len(raw) <= MAX_PROMPT_IMAGE_BYTES:
        return raw, path.suffix.lstrip(".") or "jpeg"
    if _ffmpeg_available():
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "thumb.jpg"
            proc = _run_ffmpeg(
                ["ffmpeg", "-y", "-i", str(path), "-vf", "scale='min(1280,iw)':-2", "-q:v", "8", str(out)],
                timeout=40,
            )
            if proc.returncode == 0 and out.is_file() and out.stat().st_size <= MAX_PROMPT_IMAGE_BYTES:
                return out.read_bytes(), "jpeg"
    if len(raw) > MAX_PROMPT_IMAGE_BYTES:
        raise ValueError("Image too large to include in model context after resize.")
    return raw, path.suffix.lstrip(".") or "jpeg"


def extract_video_frames(path: Path, duration: float | None) -> list[dict]:
    if not _ffmpeg_available():
        return []
    dur = duration or _probe_duration(path) or 0.0
    if dur <= 0:
        dur = 30.0
    dur = min(dur, MAX_VIDEO_DURATION_S)
    count = min(MAX_VIDEO_FRAMES, max(3, int(dur // 4) + 1))
    times = [round(dur * i / max(count - 1, 1), 2) for i in range(count)]
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for idx, t in enumerate(times):
            out = Path(tmp) / f"frame_{idx}.jpg"
            proc = _run_ffmpeg(
                ["ffmpeg", "-y", "-ss", str(t), "-i", str(path), "-frames:v", "1", "-q:v", "6", str(out)],
                timeout=35,
            )
            if proc.returncode != 0 or not out.is_file():
                continue
            blob = out.read_bytes()
            if len(blob) > MAX_PROMPT_IMAGE_BYTES:
                continue
            frames.append({"time_s": t, "mime": "image/jpeg", "data_base64": base64.b64encode(blob).decode()})
    return frames


def extract_audio_transcript(path: Path) -> str:
    if not _ffmpeg_available():
        return ""
    whisper = shutil.which("whisper") or shutil.which("whisper-cli")
    if not whisper:
        return ""
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        proc = _run_ffmpeg(
            ["ffmpeg", "-y", "-i", str(path), "-ac", "1", "-ar", "16000", "-t", str(MAX_VIDEO_DURATION_S), str(wav)],
            timeout=60,
        )
        if proc.returncode != 0 or not wav.is_file():
            return ""
        try:
            out = subprocess.run(
                [whisper, str(wav), "--model", "tiny", "--output_format", "txt", "--output_dir", tmp, "--language", "en"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        if out.returncode != 0:
            return ""
        for txt in Path(tmp).glob("*.txt"):
            text = txt.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                return text[:8000]
    return ""


def describe_video(path: Path) -> dict:
    duration = _probe_duration(path)
    frames = extract_video_frames(path, duration)
    transcript = extract_audio_transcript(path)
    return {
        "duration_s": duration,
        "frame_count": len(frames),
        "frames": frames,
        "transcript": transcript,
    }


def read_text_file(path: Path, limit: int = 12000) -> str:
    try:
        raw = path.read_bytes()[: limit + 1]
    except OSError:
        return ""
    if b"\x00" in raw[:4096]:
        return "[binary file; text excerpt unavailable]"
    return raw[:limit].decode("utf-8", errors="replace")


def enrich_for_model(root: Path, metas: list[dict]) -> dict:
    """Build model-facing attachment bundle (text + optional vision parts)."""
    text_blocks: list[str] = []
    vision: list[dict] = []
    for meta in metas:
        path = resolve_media(root, meta["media_id"])
        kind = meta.get("kind") or classify_suffix(path.suffix)
        label = meta.get("filename") or path.name
        if kind == "image":
            try:
                blob, fmt = prompt_image_bytes(path)
            except ValueError as exc:
                text_blocks.append(f"Image {label}: {exc}")
                continue
            mime = f"image/{'jpeg' if fmt == 'jpg' else fmt}"
            b64 = base64.b64encode(blob).decode()
            size = _image_size(blob)
            dim = f"{size[0]}x{size[1]}" if size else "unknown size"
            text_blocks.append(f"Image attachment {label} ({dim}, {mime}). Jeff shared this image for you to see.")
            vision.append({"mime": mime, "data_base64": b64, "caption": label})
        elif kind == "video":
            info = describe_video(path)
            dur = info.get("duration_s")
            dur_s = f"{dur:.1f}s" if isinstance(dur, (int, float)) else "unknown duration"
            text_blocks.append(f"Video attachment {label} ({dur_s}). Sampled {info['frame_count']} frame(s).")
            if info.get("transcript"):
                text_blocks.append("Video audio transcript:\n" + info["transcript"])
            else:
                text_blocks.append("Video audio transcript: (none — whisper/ffmpeg unavailable or silent clip).")
            for frame in info.get("frames") or []:
                vision.append({
                    "mime": frame["mime"],
                    "data_base64": frame["data_base64"],
                    "caption": f"{label} @ {frame['time_s']}s",
                })
        else:
            excerpt = read_text_file(path)
            text_blocks.append(f"File attachment {label} ({meta.get('bytes', path.stat().st_size)} bytes):\n{excerpt}")
    return {"text": "\n\n".join(text_blocks).strip(), "vision": vision}


def strip_assistant_attachment_markers(content: str) -> tuple[str, list[dict]]:
    attachments: list[dict] = []
    for match in ATTACHMENT_TAG.finditer(content):
        attachments.append({"media_id": match.group(1), "label": match.group(2) or ""})
    cleaned = ATTACHMENT_TAG.sub("", content).strip()
    for match in MEDIA_LINK.finditer(content):
        attachments.append({"media_id": match.group(1), "label": ""})
    return cleaned, attachments


def public_attachment(meta: dict) -> dict:
    return {
        "media_id": meta["media_id"],
        "filename": meta.get("filename") or meta["media_id"],
        "kind": meta.get("kind", "file"),
        "url": meta.get("url") or f"/api/media/{meta['media_id']}",
        "bytes": meta.get("bytes", 0),
    }

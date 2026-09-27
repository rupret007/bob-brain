#!/usr/bin/env python3
"""MiniMax music sketch generation with metered cap and handback logging."""
from __future__ import annotations

import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path

from handback import append_turn

ROOT = Path(__file__).resolve().parents[2]
MUSIC_ESTIMATE_USD = 0.04
UPLOADS = Path("conductor/webchat/uploads")
ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}


def _upload_dir(root: Path) -> Path:
    path = root / UPLOADS
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_keys(root: Path) -> None:
    path = root / "conductor/keys.env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        name, sep, value = line.removeprefix("export ").partition("=")
        if sep and re.fullmatch(r"[A-Z_][A-Z0-9_]*", name.strip()):
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def assert_music_budget_headroom(root: Path) -> None:
    import sys
    sys.path.insert(0, str(root / "conductor/webchat"))
    sys.path.insert(0, str(root / "conductor/services"))
    load_keys(root)
    import budget
    import billing as chat_billing
    chat_billing.enforce_chat_cap(budget)
    cap = min(budget.CAP_USD, chat_billing.MINIMAX_CAP_USD)
    totals = budget.totals("minimax")
    if totals["committed_usd"] + MUSIC_ESTIMATE_USD > cap:
        raise budget.BudgetExceeded("MiniMax cap: music demo does not fit")


def charge_music_budget(root: Path) -> None:
    import sys
    import uuid
    sys.path.insert(0, str(root / "conductor/webchat"))
    sys.path.insert(0, str(root / "conductor/services"))
    load_keys(root)
    import budget
    import billing as chat_billing
    chat_billing.enforce_chat_cap(budget)
    cap = min(budget.CAP_USD, chat_billing.MINIMAX_CAP_USD)
    with budget.lock("ledger-minimax"):
        calls = {r["call_id"]: r for r in budget._rows(budget.path("minimax"))}
        committed = sum(r["cost_usd"] if r.get("cost_usd") is not None else r.get("reserved_usd", 0) for r in calls.values())
        if committed + MUSIC_ESTIMATE_USD > cap:
            raise budget.BudgetExceeded("MiniMax cap: music demo does not fit")
        budget._append(budget.path("minimax"), {"call_id": uuid.uuid4().hex, "event": "music", "lane": "minimax",
                                                "cost_usd": MUSIC_ESTIMATE_USD, "reserved_usd": 0,
                                                "purpose": "webchat-music", "timestamp": time.time()})


def generate_demo(root: Path, *, lyrics: str, style: str, dry_run: bool = False) -> dict:
    lyrics = lyrics.strip()[:4000]
    style = style.strip()[:500] or "acoustic singer-songwriter, warm, mid-tempo"
    if not lyrics:
        raise ValueError("Lyrics are required for a demo sketch.")
    if dry_run:
        return {"ok": True, "dry_run": True, "estimated_usd": MUSIC_ESTIMATE_USD, "style": style, "lyrics_chars": len(lyrics)}
    assert_music_budget_headroom(root)
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MiniMax API key is not configured.")
    body = json.dumps({
        "model": "music-01",
        "prompt": style,
        "lyrics": lyrics,
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3"},
        "output_format": "hex",
    }).encode()
    request = urllib.request.Request(
        "https://api.minimax.io/v1/music_generation",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"MiniMax music API error ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MiniMax music network error: {exc.reason}") from exc
    audio_hex = ""
    if isinstance(payload.get("data"), dict):
        audio_hex = payload["data"].get("audio") or payload["data"].get("audio_file") or ""
    if not audio_hex and isinstance(payload.get("audio"), str):
        audio_hex = payload["audio"]
    if not audio_hex:
        raise RuntimeError("MiniMax returned no audio payload.")
    raw = bytes.fromhex(audio_hex) if re.fullmatch(r"[0-9a-fA-F]+", audio_hex.strip()) else audio_hex.encode()
    if not raw[:4]:
        raise RuntimeError("MiniMax audio payload was empty.")
    name = secrets.token_hex(8) + ".mp3"
    path = _upload_dir(root) / name
    path.write_bytes(raw)
    os.chmod(path, 0o600)
    charge_music_budget(root)
    append_turn(root, ask=f"music demo: {style[:120]}", provider="minimax-music", jobs=[], files=[str(path.relative_to(root))],
                commits=[], confirmations=[], refusals=[], open_items=[f"demo cost ~${MUSIC_ESTIMATE_USD:.4f}"])
    return {"ok": True, "audio_id": name.removesuffix(".mp3"), "path": str(path.relative_to(root)),
            "cost_usd": MUSIC_ESTIMATE_USD, "bytes": len(raw)}


def store_upload(root: Path, data: bytes, suffix: str) -> dict:
    suffix = suffix.lower() if suffix.startswith(".") else "." + suffix.lower()
    if suffix not in ALLOWED_AUDIO:
        raise ValueError("Unsupported audio type.")
    if len(data) > 25 * 1024 * 1024:
        raise ValueError("Audio file too large (25MB max).")
    token = secrets.token_hex(8)
    path = _upload_dir(root) / (token + suffix)
    path.write_bytes(data)
    os.chmod(path, 0o600)
    return {"audio_id": token, "path": str(path.relative_to(root)), "bytes": len(data)}


def resolve_audio(root: Path, audio_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{16}", audio_id):
        raise ValueError("Invalid audio id.")
    folder = _upload_dir(root)
    for suffix in ALLOWED_AUDIO:
        path = folder / (audio_id + suffix)
        if path.exists():
            return path
    raise FileNotFoundError(audio_id)

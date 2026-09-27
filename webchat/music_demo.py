#!/usr/bin/env python3
"""MiniMax music sketch generation with metered cap and handback logging."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from handback import append_turn
from music_local_sketch import render_sketch

ROOT = Path(__file__).resolve().parents[2]
MUSIC_ENDPOINTS = (
    "https://api.minimax.io/v1/music_generation",
)
MUSIC_MODELS = ("music-3.0", "music-01")
MUSIC_ESTIMATE_USD = 0.04
MAX_UPLOAD_BYTES = 35 * 1024 * 1024
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


def demo_receipt(lyrics: str, style: str) -> str:
    digest = hashlib.sha256((lyrics.strip() + "\0" + style.strip()).encode("utf-8")).hexdigest()
    return digest[:20]


def _budget_paths(root: Path) -> None:
    import sys
    services = str(root / "conductor/services")
    if services not in sys.path:
        sys.path.insert(0, services)
    webchat = str(root / "conductor/webchat")
    if webchat not in sys.path:
        sys.path.insert(0, webchat)


def music_budget_status(root: Path) -> dict:
    _budget_paths(root)
    load_keys(root)
    import budget
    import billing as chat_billing
    chat_billing.enforce_chat_cap(budget)
    cap = min(budget.CAP_USD, chat_billing.MINIMAX_CAP_USD)
    totals = budget.totals("minimax")
    remaining = max(0.0, cap - totals["committed_usd"])
    return {"cap_usd": cap, "committed_usd": totals["committed_usd"], "remaining_usd": round(remaining, 4),
            "demo_estimate_usd": MUSIC_ESTIMATE_USD, "can_afford_demo": remaining >= MUSIC_ESTIMATE_USD}


def assert_music_budget_headroom(root: Path) -> None:
    _budget_paths(root)
    load_keys(root)
    import budget
    import billing as chat_billing
    chat_billing.enforce_chat_cap(budget)
    cap = min(budget.CAP_USD, chat_billing.MINIMAX_CAP_USD)
    totals = budget.totals("minimax")
    if totals["committed_usd"] + MUSIC_ESTIMATE_USD > cap:
        raise budget.BudgetExceeded("MiniMax cap: music demo does not fit")


def _reserve_music_budget(root: Path) -> str:
    _budget_paths(root)
    load_keys(root)
    import budget
    import billing as chat_billing
    chat_billing.enforce_chat_cap(budget)
    cap = min(budget.CAP_USD, chat_billing.MINIMAX_CAP_USD)
    call_id = uuid.uuid4().hex
    with budget.lock("ledger-minimax"):
        calls = {r["call_id"]: r for r in budget._rows(budget.path("minimax"))}
        committed = sum(r["cost_usd"] if r.get("cost_usd") is not None else r.get("reserved_usd", 0) for r in calls.values())
        if committed + MUSIC_ESTIMATE_USD > cap:
            raise budget.BudgetExceeded("MiniMax cap: music demo does not fit")
        row = {"call_id": call_id, "event": "reserved", "lane": "minimax", "reserved_usd": MUSIC_ESTIMATE_USD,
               "cost_usd": None, "purpose": "webchat-music", "timestamp": time.time()}
        budget._append(budget.path("minimax"), row)
    return call_id


def _finalize_music_budget(root: Path, call_id: str, *, charged: bool) -> None:
    _budget_paths(root)
    import budget
    with budget.lock("ledger-minimax"):
        if charged:
            budget._append(budget.path("minimax"), {"call_id": call_id, "event": "music", "lane": "minimax",
                                                    "cost_usd": MUSIC_ESTIMATE_USD, "reserved_usd": 0,
                                                    "purpose": "webchat-music", "timestamp": time.time()})
        else:
            budget._append(budget.path("minimax"), {"call_id": call_id, "event": "cancel", "lane": "minimax",
                                                    "cost_usd": 0.0, "reserved_usd": 0,
                                                    "purpose": "webchat-music", "timestamp": time.time()})


def _try_replicate(root: Path, *, lyrics: str, style: str) -> dict | None:
    token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not token:
        return None
    body = json.dumps({
        "input": {
            "lyrics": lyrics[:4000],
            "prompt": style[:500],
        },
    }).encode()
    request = urllib.request.Request(
        "https://api.replicate.com/v1/models/minimax/music-01/predictions",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Prefer": "wait"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None
    output = payload.get("output")
    url = output if isinstance(output, str) else (output[0] if isinstance(output, list) and output else None)
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=120) as audio_response:
            raw = audio_response.read()
    except urllib.error.URLError:
        return None
    if len(raw) < 128:
        return None
    name = secrets.token_hex(8) + ".mp3"
    path = _upload_dir(root) / name
    path.write_bytes(raw)
    os.chmod(path, 0o600)
    return {"ok": True, "audio_id": name.removesuffix(".mp3"), "path": str(path.relative_to(root)),
            "bytes": len(raw), "engine": "replicate-music-01", "cost_usd": MUSIC_ESTIMATE_USD}


def _try_minimax_hosted(root: Path, *, lyrics: str, style: str) -> dict | None:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        return None
    for url in MUSIC_ENDPOINTS:
        for model in MUSIC_MODELS:
            body = json.dumps({
                "model": model,
                "prompt": style,
                "lyrics": lyrics,
                "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3"},
                "output_format": "hex",
            }).encode()
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = json.loads(response.read().decode())
            except urllib.error.HTTPError as exc:
                if exc.code in (410, 403, 404):
                    continue
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
                continue
            raw = bytes.fromhex(audio_hex) if re.fullmatch(r"[0-9a-fA-F]+", audio_hex.strip()) else audio_hex.encode()
            if len(raw) < 128:
                continue
            name = secrets.token_hex(8) + ".mp3"
            path = _upload_dir(root) / name
            path.write_bytes(raw)
            os.chmod(path, 0o600)
            return {"ok": True, "audio_id": name.removesuffix(".mp3"), "path": str(path.relative_to(root)),
                    "bytes": len(raw), "engine": f"minimax-{model}", "cost_usd": MUSIC_ESTIMATE_USD}
    return None


def generate_demo(root: Path, *, lyrics: str, style: str, dry_run: bool = False) -> dict:
    lyrics = lyrics.strip()[:4000]
    style = style.strip()[:500] or "acoustic singer-songwriter, warm, mid-tempo"
    if not lyrics:
        raise ValueError("Lyrics are required for a demo sketch.")
    if dry_run:
        try:
            status = music_budget_status(root)
        except (ImportError, OSError, ModuleNotFoundError):
            status = {"cap_usd": 59.0, "committed_usd": 0.0, "remaining_usd": 59.0,
                      "demo_estimate_usd": MUSIC_ESTIMATE_USD, "can_afford_demo": True}
        return {"ok": True, "dry_run": True, "estimated_usd": MUSIC_ESTIMATE_USD, "style": style, "lyrics_chars": len(lyrics),
                "receipt": demo_receipt(lyrics, style), **status}
    call_id = _reserve_music_budget(root)
    try:
        result = _try_minimax_hosted(root, lyrics=lyrics, style=style)
        if result is None:
            result = _try_replicate(root, lyrics=lyrics, style=style)
        if result is None:
            _finalize_music_budget(root, call_id, charged=False)
            result = render_sketch(root, lyrics=lyrics, style=style)
            append_turn(root, ask=f"music demo (local sketch): {style[:120]}", provider="local-sketch", jobs=[],
                        files=[result["path"]], commits=[], confirmations=[], refusals=[],
                        open_items=[result.get("note", "")[:200]])
            return result
        charged = float(result.get("cost_usd") or 0) > 0
        _finalize_music_budget(root, call_id, charged=charged)
        append_turn(root, ask=f"music demo: {style[:120]}", provider=result.get("engine", "minimax-music"), jobs=[],
                    files=[result["path"]], commits=[], confirmations=[], refusals=[],
                    open_items=[f"demo cost ~${result.get('cost_usd', MUSIC_ESTIMATE_USD):.4f}"])
        return result
    except Exception:
        _finalize_music_budget(root, call_id, charged=False)
        raise


def store_upload(root: Path, data: bytes, suffix: str) -> dict:
    suffix = suffix.lower() if suffix.startswith(".") else "." + suffix.lower()
    if suffix not in ALLOWED_AUDIO:
        raise ValueError("Unsupported audio type.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Audio file too large (35MB max).")
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

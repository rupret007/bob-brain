#!/usr/bin/env python3
"""Honest offline chord sketch when hosted MiniMax music is not entitled."""
from __future__ import annotations

import hashlib
import math
import secrets
import struct
import wave
from pathlib import Path

UPLOADS = Path("conductor/webchat/uploads")


def _upload_dir(root: Path) -> Path:
    path = root / UPLOADS
    path.mkdir(parents=True, exist_ok=True)
    return path

CHORDS = {
    "major": [(261.63, 329.63, 392.0), (293.66, 369.99, 440.0), (329.63, 415.30, 493.88), (349.23, 440.0, 523.25)],
    "folk": [(220.0, 261.63, 329.63), (246.94, 293.66, 369.99), (196.0, 246.94, 293.66), (174.61, 220.0, 261.63)],
    "rock": [(146.83, 185.0, 220.0), (164.81, 207.65, 246.94), (130.81, 164.81, 196.0), (123.47, 155.56, 185.0)],
}


def _pick_progression(style: str) -> list[tuple[float, float, float]]:
    key = "folk"
    lower = style.lower()
    if "rock" in lower or "electric" in lower:
        key = "rock"
    elif "pop" in lower or "bright" in lower:
        key = "major"
    digest = hashlib.sha256(style.encode()).digest()
    base = CHORDS[key]
    rotate = digest[0] % len(base)
    return [base[(rotate + i) % len(base)] for i in range(4)]


def render_sketch(root: Path, *, lyrics: str, style: str) -> dict:
    sr = 32000
    bar = int(sr * 2.2)
    progression = _pick_progression(style)
    samples: list[int] = []
    for chord in progression * 3:
        for i in range(bar):
            t = i / sr
            env = min(1.0, i / (sr * 0.05)) * min(1.0, (bar - i) / (sr * 0.12))
            value = sum(math.sin(2 * math.pi * f * t) for f in chord) / len(chord)
            samples.append(int(max(-1.0, min(1.0, value * env * 0.35)) * 32767))
    name = secrets.token_hex(8) + ".wav"
    path = _upload_dir(root) / name
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    path.chmod(0o600)
    lines = [line.strip() for line in lyrics.splitlines() if line.strip()][:4]
    return {
        "ok": True,
        "audio_id": name.removesuffix(".wav"),
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "engine": "local-sketch",
        "cost_usd": 0.0,
        "note": (
            "Hosted MiniMax music is not entitled on this account; this is a local chord sketch "
            "(not a vocal AI demo). Lyrics saved: " + ("; ".join(lines) if lines else "(none)") + "."
        ),
    }

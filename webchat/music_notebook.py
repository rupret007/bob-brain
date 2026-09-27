#!/usr/bin/env python3
"""Persistent song projects for Web Bob (lyrics, chords, notes, versions)."""
from __future__ import annotations

import json
import os
import re
import secrets
import time
import uuid
from pathlib import Path

PROJECT_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

FOLDER = Path("conductor/webchat/song-projects")
INDEX = "index.json"
MAX_BODY = 120_000


def _dir(root: Path) -> Path:
    path = root / FOLDER
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, value: str) -> None:
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(6))
    try:
        with open(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_index(root: Path) -> dict:
    path = _dir(root) / INDEX
    if not path.exists():
        return {"projects": []}
    return json.loads(path.read_text())


def _save_index(root: Path, data: dict) -> None:
    _write(_dir(root) / INDEX, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def list_projects(root: Path) -> list[dict]:
    data = _load_index(root)
    rows = sorted(data.get("projects", []), key=lambda row: row.get("updated_at", 0), reverse=True)
    return [{k: row[k] for k in ("id", "title", "updated_at", "created_at") if k in row} for row in rows]


def get_project(root: Path, project_id: str) -> dict:
    if not PROJECT_ID.fullmatch(project_id):
        raise FileNotFoundError(project_id)
    path = _dir(root) / f"{project_id}.json"
    if not path.exists():
        raise FileNotFoundError(project_id)
    return json.loads(path.read_text())


def save_project(root: Path, payload: dict) -> dict:
    title = (payload.get("title") or "Untitled song").strip()[:120]
    lyrics = (payload.get("lyrics") or "")[:MAX_BODY]
    chords = (payload.get("chords") or "")[:MAX_BODY]
    notes = (payload.get("notes") or "")[:MAX_BODY]
    project_id = payload.get("id")
    now = time.time()
    if project_id and not PROJECT_ID.fullmatch(project_id):
        raise ValueError("invalid project id")
    if len(lyrics.strip()) + len(chords.strip()) < 3 and not project_id:
        raise ValueError("Add a few characters of lyrics or chords before saving.")
    if project_id:
        project = get_project(root, project_id)
        project.update(title=title, lyrics=lyrics, chords=chords, notes=notes, updated_at=now)
    else:
        project_id = str(uuid.uuid4())
        project = {"id": project_id, "title": title, "lyrics": lyrics, "chords": chords, "notes": notes,
                   "created_at": now, "updated_at": now, "versions": []}
    if payload.get("version_note"):
        project.setdefault("versions", []).append(
            {"at": now, "note": str(payload["version_note"])[:500], "lyrics": lyrics[:8000]})
        project["versions"] = project["versions"][-30:]
    _write(_dir(root) / f"{project_id}.json", json.dumps(project, ensure_ascii=False, indent=2) + "\n")
    data = _load_index(root)
    rows = [row for row in data.get("projects", []) if row.get("id") != project_id]
    rows.append({"id": project_id, "title": title, "created_at": project["created_at"], "updated_at": now})
    _save_index(root, {"projects": rows})
    return project


def snapshot_for_prompt(root: Path, limit: int = 6000) -> str:
    lines = []
    for row in list_projects(root)[:8]:
        try:
            project = get_project(root, row["id"])
            snippet = (project.get("lyrics") or "").strip().splitlines()
            preview = "\n".join(snippet[:12])
            chords = (project.get("chords") or "").strip().splitlines()
            chord_line = "\n".join(chords[:4])
            notes = (project.get("notes") or "").strip()[:400]
            block = f"### {project['title']} ({project['id'][:8]})\n{preview}"
            if chord_line:
                block += f"\nChords: {chord_line}"
            if notes:
                block += f"\nNotes: {notes}"
            lines.append(block)
        except (OSError, json.JSONDecodeError, KeyError):
            lines.append(f"### (corrupt project {row.get('id', '?')[:8]}) — fix in Song panel")
            continue
    text = "\n\n".join(lines)
    return text[:limit]


_MUSIC_COACH_RE = re.compile(
    r"\b(?:(?:my |a )?song|lyrics|chorus|verse|bridge|hook|chords?|progression|melody|arrange|rhyme|meter)\b",
    re.I,
)


def try_music_coach_reply(text: str) -> str | None:
    """Cheap songwriting partner tips (no API spend)."""
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 280 or not _MUSIC_COACH_RE.search(stripped):
        return None
    lower = stripped.lower()
    if "chord" in lower or "progression" in lower:
        return (
            "For chords, try a simple loop (verse: I–V–vi–IV, chorus lift to IV or vi). "
            "Match the mood in the Songs tab — save a version after each pass. "
            "Local sketch demo ($0) can render a rough MP3 from lyrics + style when you are ready."
        )
    if "chorus" in lower or "hook" in lower:
        return (
            "Chorus tip: one clear emotional line, repeat the title, keep lines short for singing. "
            "Contrast with the verse (higher energy or wider melody). "
            "Drop a draft in Songs → lyrics, then ask me to tighten a specific line."
        )
    return (
        "Song structure: verse → chorus → verse → chorus → bridge → chorus is a solid default. "
        "Use the Songs tab for lyrics/chords/versions; I can rewrite lines, rhyme, or arrangement notes here. "
        "No MiniMax music API — local sketch + Logic (confirm-first) when you want audio on the mini."
    )

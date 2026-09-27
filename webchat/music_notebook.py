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
    r"\b(?:(?:my |a )?song|lyrics|chorus|verse|bridge|hook|chords?|progression|melody|arrange|rhyme|meter|tempo|bpm|structure|time signature|4/4|3/4|6/8|modulation|key change|outro|fade|ending|pre[- ]?chorus|post[- ]?chorus|double[- ]?chorus|tag[- ]?line|tagline|capo|riffs?|vamp|dynamics?|breakdown|build[- ]?up|drop)\b",
    re.I,
)


def try_music_coach_reply(text: str) -> str | None:
    """Cheap songwriting partner tips (no API spend)."""
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 280 or not _MUSIC_COACH_RE.search(stripped):
        return None
    lower = stripped.lower()
    if "modulation" in lower or "key change" in lower:
        return (
            "Modulation: move up a half-step or whole-step for the final chorus lift (common in pop). "
            "Set up with a dominant chord (V) of the new key one bar before the change — e.g. G7 before C major. "
            "Note old and new keys in Songs → notes so versions and Bob stay aligned."
        )
    music_ctx = re.search(
        r"\b(song|lyrics|chorus|verse|guitar|track|riff|hook|arrange)\b",
        lower,
    )
    if re.search(r"\bintro\b", lower) and music_ctx:
        return (
            "Intro: one riff or motif that foreshadows the chorus hook — keep it 4–8 bars, no lyrics required. "
            "Drop the energy after bar 4 so verse 1 feels like a breath. "
            "Note the intro idea in Songs → notes; Logic markers are confirm-first."
        )
    if "pre-chorus" in lower or "prechorus" in lower or "pre chorus" in lower:
        return (
            "Pre-chorus: build tension with rising chords (e.g. vi–IV–V) and a shorter melodic line than the verse. "
            "Land on the dominant (V) right before the chorus downbeat. "
            "Save lyric tweaks as a new Songs version so Bob sees the lift."
        )
    if "capo" in lower:
        return (
            "Capo: match the singer’s comfortable range — write shapes in friendly keys (G, C, D) and note capo fret in Songs → chords. "
            "Same chord names on paper; the sounding key shifts up. "
            "Record which fret you used in notes for the handback."
        )
    if re.search(r"\b(dynamic|breakdown|build[- ]?up|drop)\b", lower):
        if not music_ctx:
            return None
        return (
            "Dynamics: verse stays lean (guitar + vocal), pre-chorus adds bass or pad, chorus full band. "
            "Breakdown = strip to one instrument for 4–8 bars before the final lift. "
            "Note the map in Songs → notes; Logic level automation is confirm-first."
        )
    if "double chorus" in lower or "post-chorus" in lower or "post chorus" in lower:
        return (
            "Double chorus: play the full chorus twice back-to-back; lift drums or harmony on the second pass. "
            "A post-chorus can be instrumental (hook riff only) between verse and chorus. "
            "Note the map in Songs → notes; Logic arrangement is confirm-first."
        )
    if "tag line" in lower or "tagline" in lower or ("chorus" in lower and "tag" in lower):
        return (
            "Tag line: repeat one hook phrase after the chorus (often the title) — 2–4 words max, same melody as the chorus hook. "
            "Use it on the outro vamp or double-chorus ending. "
            "Save the tag lyric as a new Songs version so Bob sees the final hook."
        )
    if "riff" in lower or "vamp" in lower:
        return (
            "Riff/vamp: repeat a 1–2 bar figure; change one note on the 4th repeat for motion. "
            "Use it under the chorus tag or as an outro fade. "
            "Hum it into Songs audio upload if you want a reference take ($0 local sketch later)."
        )
    if "outro" in lower or "ending" in lower or "fade" in lower:
        return (
            "Outro: repeat the chorus hook once, strip instruments for the last line, or tag a new lyric over the vamp. "
            "A fade works on sketch demos; in Logic, mark the outro region confirm-first before bounce. "
            "Save the lyric tweak as a new Songs version."
        )
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
    if "rhyme" in lower or "meter" in lower:
        return (
            "Rhyme without forcing: pick one rhyme sound per section (e.g. -ay) and leave one line unrhymed for breath. "
            "For meter, read lines aloud and trim syllables until stresses land on beats 1 and 3 in 4/4. "
            "Save a version in Songs after each rewrite so Bob sees the history."
        )
    if "melody" in lower or "arrange" in lower:
        return (
            "Melody: start with the chorus on fewer notes than the verse; leave space at phrase ends. "
            "Arrangement: add one layer at a time (guitar → bass → pad). "
            "Use Songs for structure notes; Logic on the mini is confirm-first for tempo/markers/bounce."
        )
    if "bridge" in lower or "structure" in lower or "verse" in lower:
        return (
            "Structure: verse sets the story, chorus is the emotional headline, bridge is one new angle before the final chorus. "
            "Try 8-bar sections in 4/4; label them in Songs → notes so versions stay clear. "
            "When a section feels long, cut a line instead of adding chords."
        )
    if "time signature" in lower or "4/4" in lower or "3/4" in lower or "6/8" in lower:
        return (
            "Time signature: 4/4 is the default pop/rock feel; 6/8 gives a lilting triplet groove; 3/4 is waltz. "
            "Keep the lyric syllables per bar consistent once you pick one. "
            "Note the choice in Songs → notes so Bob and versions stay aligned."
        )
    if "tempo" in lower or "bpm" in lower or ("key" in lower and "change" not in lower):
        return (
            "Tempo/key: pick BPM in Songs notes (e.g. 92 BPM, key of G). "
            "Match chord voicings to the singer’s comfortable range; capo is fine. "
            "Upload a rough take in Songs for reference — local sketch demo can follow lyrics + style ($0)."
        )
    return (
        "Song structure: verse → chorus → verse → chorus → bridge → chorus is a solid default. "
        "Use the Songs tab for lyrics/chords/versions; I can rewrite lines, rhyme, or arrangement notes here. "
        "No MiniMax music API — local sketch + Logic (confirm-first) when you want audio on the mini."
    )

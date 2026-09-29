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
    r"\b(?:(?:my |a )?song|lyrics|chorus|verse|bridge|hook|chords?|progression|melody|arrange|rhyme|meter|tempo|bpm|structure|time signature|4/4|3/4|6/8|modulation|key change|nashville|number system|outro|fade|ending|pre[- ]?chorus|post[- ]?chorus|double[- ]?chorus|tag[- ]?line|tagline|refrain|capo|riffs?|vamp|dynamics?|breakdown|build[- ]?up|drop|cadence|deceptive)\b",
    re.I,
)

_VOWEL_RUN = re.compile(r"[aeiouy]+", re.I)


def _syllables_in_word(word: str) -> int:
    cleaned = re.sub(r"[^a-zA-Z']", "", word).lower()
    if not cleaned:
        return 0
    if len(cleaned) <= 3:
        return 1
    groups = _VOWEL_RUN.findall(cleaned)
    count = len(groups)
    if cleaned.endswith("e") and count > 1 and not cleaned.endswith("le"):
        count -= 1
    if cleaned.endswith("ed") and count > 1 and not cleaned.endswith("ted") and not cleaned.endswith("ded"):
        count -= 1
    return max(1, count)


def _syllables_in_line(line: str) -> int:
    return sum(_syllables_in_word(part) for part in line.split())


def _strip_meter_prompt_line(line: str) -> str:
    cleaned = re.sub(
        r"^(?:please\s+)?(?:count|check|scan)\s+(?:the\s+)?(?:syllables?|meter|metre|scansion)\s+(?:in|on|for)\s+",
        "",
        line.strip(),
        flags=re.I,
    )
    cleaned = re.sub(r"^(?:my\s+)?(?:verse\s+)?lyrics?\s*:?\s*", "", cleaned, flags=re.I).strip()
    return cleaned


def _extract_lyric_lines(text: str) -> list[str]:
    stripped = (text or "").strip()
    if not stripped:
        return []
    if "\n" in stripped:
        raw = [ln.strip() for ln in stripped.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        if raw and re.search(r"\b(syllable|meter|metre|scansion|count)\b", raw[0], re.I):
            raw = raw[1:]
        if raw and re.fullmatch(r"(?:please\s+)?(?:rhyme\s+scan|check\s+rhymes?)\s*:?", raw[0], re.I):
            raw = raw[1:]
        if raw and re.search(r"\brhyme\s+scan\b", raw[0], re.I) and ":" in raw[0] and len(raw[0]) < 120:
            raw = raw[1:]
        return [_strip_meter_prompt_line(ln) for ln in raw if _strip_meter_prompt_line(ln)]
    if ":" in stripped:
        tail = stripped.split(":", 1)[1].strip()
        if "\n" in tail:
            return [ln.strip() for ln in tail.splitlines() if ln.strip()]
        if len(tail) > 12 and re.search(r"\b(verse|lyrics|chorus|line)\b", stripped, re.I):
            parts = re.split(r"\s*/\s*|\s*\|\s*", tail)
            if len(parts) >= 2:
                return [p.strip() for p in parts if p.strip()]
    quoted = re.findall(r"[\"']([^\"']{8,})[\"']", stripped)
    if quoted:
        block = max(quoted, key=len)
        if "\n" in block:
            return [ln.strip() for ln in block.splitlines() if ln.strip()]
        return [block.strip()]
    return []


def _rhyme_tail(word: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z']", "", word).lower()
    if len(cleaned) < 2:
        return cleaned
    tail = cleaned[-3:] if len(cleaned) >= 3 else cleaned
    return _normalize_rime_tail(tail)


def _normalize_rime_tail(tail: str) -> str:
    """Approximate rime families for $0 scan (not dictionary phonetics)."""
    if not tail:
        return tail
    if tail in ("ane", "ain"):
        return "ain"
    if tail.endswith("ne") and "a" in tail:
        return "ain"
    if tail.endswith("ay") or tail.endswith("ey") or tail in ("y", "ie"):
        return "ay"
    if tail.endswith("ight") or tail.endswith("ite"):
        return "ite"
    return tail


_CHORD_SYM = re.compile(
    r"\b([A-G][#b]?(?:maj7|min7|m7|maj|min|dim|aug|sus2|sus4|add9|m)?)\b",
    re.I,
)


def analyze_chord_progression(text: str) -> str | None:
    """Parse pasted chord symbols and sketch roman numerals ($0, no API)."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    lower = stripped.lower()
    explicit = re.search(
        r"\b(chord progression|progression scan|analyze (?:this )?progression|roman numerals?|parse chords?)\b",
        lower,
    )
    symbols = [m.group(1) for m in _CHORD_SYM.finditer(stripped)]
    if not explicit and len(symbols) < 3:
        return None
    if len(symbols) < 2:
        return None
    symbols = symbols[:12]
    major_map = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    flat_map = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

    def _root_index(sym: str) -> int | None:
        m = re.match(r"^([A-G][#b]?)", sym)
        if not m:
            return None
        r = m.group(1)
        if len(r) == 2 and r[1] == "b":
            r = flat_map.get(r[:1] + "b", r)
        return major_map.get(r)

    def _is_minor(sym: str) -> bool:
        s = sym.lower()
        return "min" in s or sym.endswith("m")

    tonic = _root_index(symbols[0])
    if tonic is None:
        return None
    scale_major = [0, 2, 4, 5, 7, 9, 11]
    numerals: list[str] = []
    for sym in symbols:
        idx = _root_index(sym)
        if idx is None:
            numerals.append("?")
            continue
        step = (idx - tonic) % 12
        try:
            degree = scale_major.index(step) + 1
        except ValueError:
            numerals.append("?")
            continue
        minor = _is_minor(sym)
        if degree == 1:
            numerals.append("i" if minor else "I")
        elif degree == 4:
            numerals.append("iv" if minor else "IV")
        elif degree == 5:
            numerals.append("v" if minor else "V")
        elif degree == 6:
            numerals.append("vi" if minor else "VI")
        elif degree == 7:
            numerals.append("vii°" if minor else "VII")
        else:
            numerals.append(f"{degree}{'m' if minor else ''}")
    roman = " – ".join(numerals)
    loop = " – ".join(symbols)
    vi_step = 9
    rel_idx = (tonic + vi_step) % 12
    inv_major = {v: k for k, v in major_map.items()}
    rel_root = inv_major.get(rel_idx)
    relative_minor = f"{rel_root}m" if rel_root else None
    tonic_line = f"Tonic: {symbols[0]} (I of {symbols[0]} major).\n"
    rel_line = (
        f"Relative minor: {relative_minor} (vi of {symbols[0]} major).\n"
        if relative_minor
        else ""
    )
    v_step = 7
    dom_idx = (tonic + v_step) % 12
    dom_root = inv_major.get(dom_idx)
    dom_line = (
        f"Dominant: {dom_root} (V of {symbols[0]} major).\n"
        if dom_root
        else ""
    )
    iv_step = 5
    sub_idx = (tonic + iv_step) % 12
    sub_root = inv_major.get(sub_idx)
    sub_line = (
        f"Subdominant: {sub_root} (IV of {symbols[0]} major).\n"
        if sub_root
        else ""
    )
    iii_step = 4
    med_idx = (tonic + iii_step) % 12
    med_root = inv_major.get(med_idx)
    med_line = (
        f"Mediant: {med_root}m (iii of {symbols[0]} major).\n"
        if med_root
        else ""
    )
    ii_step = 2
    sup_idx = (tonic + ii_step) % 12
    sup_root = inv_major.get(sup_idx)
    sup_line = (
        f"Supertonic: {sup_root}m (ii of {symbols[0]} major).\n"
        if sup_root
        else ""
    )
    vii_step = 11
    lt_idx = (tonic + vii_step) % 12
    lt_root = inv_major.get(lt_idx)
    lt_line = (
        f"Leading tone: {lt_root}dim (vii° of {symbols[0]} major).\n"
        if lt_root
        else ""
    )
    plagal_line = ""
    deceptive_line = ""
    authentic_line = ""
    half_line = ""
    for i in range(len(numerals) - 1):
        if not plagal_line and numerals[i] in ("IV", "iv") and numerals[i + 1] in ("I", "i"):
            plagal_line = "Plagal cadence: IV → I — warm amen lift before the next section.\n"
        if not deceptive_line and numerals[i] in ("V", "v") and numerals[i + 1] in ("vi", "VI"):
            deceptive_line = "Deceptive cadence: V → vi — surprise lift instead of landing on I.\n"
        if not authentic_line and numerals[i] in ("V", "v") and numerals[i + 1] in ("I", "i"):
            authentic_line = "Authentic cadence: V → I — strong full stop; great before a tag or outro.\n"
    if not authentic_line and numerals and numerals[-1] in ("V", "v"):
        half_line = "Half cadence: ends on V — tension before the chorus or tag.\n"
    if numerals[:4] == ["I", "V", "vi", "IV"] or numerals[:4] == ["I", "V", "VI", "IV"]:
        tip = "Classic pop loop — try swapping vi for a minor iv on the pre-chorus for a darker lift."
    elif all(n in ("I", "IV", "V", "vi") for n in numerals if n != "?"):
        tip = "Diatonic major family — good for singable hooks; add a passing ii–V before the chorus."
    else:
        tip = "Sketch the feel in Songs → chords; bounce a Logic scratch only after you confirm."
    return (
        f"Chord progression scan ($0, major tonic assumed from {symbols[0]}):\n"
        f"Loop: {loop}\n"
        f"Roman sketch: {roman}\n"
        f"{tonic_line}"
        f"{rel_line}"
        f"{dom_line}"
        f"{sub_line}"
        f"{med_line}"
        f"{sup_line}"
        f"{lt_line}"
        f"{plagal_line}"
        f"{deceptive_line}"
        f"{half_line}"
        f"{authentic_line}"
        f"{tip} Save each pass in Songs → versions for Bob handback."
    )


def analyze_end_rhymes(text: str) -> str | None:
    """Approximate end-rhyme groups on pasted lines ($0, no API)."""
    lower = (text or "").lower()
    wants = re.search(r"\b(rhyme scan|end rhymes?|rhyme scheme|check rhymes?)\b", lower)
    if not wants and not (re.search(r"\brhyme\b", lower) and re.search(r"\bscan\b", lower)):
        return None
    lines = _extract_lyric_lines(text)
    if len(lines) < 2:
        return None
    tails: list[str] = []
    last_words: list[str] = []
    for line in lines[:8]:
        words = re.findall(r"[a-zA-Z']+", line)
        if not words:
            tails.append("?")
            last_words.append("?")
            continue
        last_words.append(words[-1])
        tails.append(_rhyme_tail(words[-1]))
    labels: dict[str, str] = {}
    scheme: list[str] = []
    next_ord = ord("A")
    for tail in tails:
        if tail not in labels:
            labels[tail] = chr(next_ord)
            next_ord += 1
        scheme.append(labels[tail])
    scheme_str = "-".join(scheme)
    paired = sum(1 for index in range(1, len(scheme)) if scheme[index] == scheme[index - 1])
    rows = [
        f"Line {index + 1} ({scheme[index]}): …{last_words[index]} — {lines[index][:72]}"
        for index in range(len(lines[:8]))
    ]
    if len(set(scheme)) == 1:
        tip = "All lines share the same rhyme color — try a B rhyme on line 2 or 4 for contrast before the chorus."
    elif paired == 0:
        tip = "No adjacent rhymes — that's fine for narrative verses; pair lines 1–2 or 3–4 for a tighter couplet feel."
    else:
        tip = f"Scheme sketch {scheme_str} — keep one rhyme sound per section and leave one line unrhymed for breath."
    return (
        "End-rhyme scan ($0, approximate spelling families):\n"
        + "\n".join(rows)
        + f"\n{tip} Save tweaks in Songs → versions so Bob sees the pass."
    )


def analyze_lyric_meter(text: str) -> str | None:
    """Approximate syllable counts per lyric line ($0, no API)."""
    lower = (text or "").lower()
    explicit = bool(re.search(r"\bmeter scan\b", lower))
    if not explicit and not re.search(r"\b(meter|metre|syllable|scansion|scan)\b", lower) and not re.search(
        r"\bcount syllables\b", lower
    ):
        return None
    lines = _extract_lyric_lines(text)
    if len(lines) < 2 and not explicit:
        return None
    if len(lines) < 1:
        return None
    counts = [_syllables_in_line(ln) for ln in lines[:8]]
    if not counts or max(counts) < 1:
        return None
    spread = max(counts) - min(counts)
    even = spread <= 2
    rows = [f"Line {i + 1}: ~{n} syllables — {lines[i][:72]}" for i, n in enumerate(counts)]
    tip = (
        "Lines look even for 4/4 — keep stresses on beats 1 and 3."
        if even
        else f"Spread is {spread} syllables across lines — trim or pad the long lines so bars feel even in 4/4."
    )
    return (
        "Lyric meter scan ($0):\n"
        + "\n".join(rows)
        + f"\n{tip} Save tweaks in Songs → versions so Bob sees the pass."
    )


def try_music_coach_reply(text: str) -> str | None:
    """Cheap songwriting partner tips (no API spend)."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    scanned = analyze_lyric_meter(stripped)
    if scanned:
        return scanned
    rhymes = analyze_end_rhymes(stripped)
    if rhymes:
        return rhymes
    progression = analyze_chord_progression(stripped)
    if progression:
        return progression
    if len(stripped) > 420 or not _MUSIC_COACH_RE.search(stripped):
        return None
    lower = stripped.lower()
    if re.search(r"\brewrite\b", lower) and (":" in stripped or len(stripped) > 55):
        return None
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
    if "turnaround" in lower and music_ctx:
        return (
            "Turnaround: use the last 2 bars before the next section — common moves are I–vi–ii–V, I–V–vi–IV, or a ii–V back to the tonic. "
            "Keep the lyric sparse so the chords breathe. "
            "Note the turnaround in Songs → chords; run progression scan on the symbols ($0)."
        )
    if re.search(r"\bplagal\b|\bamen\s+cadence\b", lower) and music_ctx:
        return (
            "Plagal cadence (amen): IV→I — softer landing than V→I; common on gospel tags and folk outros. "
            "Try IV–I–I–V as a four-bar tag, or IV→I right before the final hook repeat. "
            "Note IV and I in Songs → chords for Bob handback ($0)."
        )
    if re.search(r"\bcadence\b", lower) and music_ctx:
        return (
            "Cadence: authentic = V→I (strong ending), plagal = IV→I (amen lift), deceptive = V→vi (surprise). "
            "End verses on half cadence (…V) to pull into the chorus. "
            "Mark which cadence you used in Songs → notes for Bob handback."
        )
    if re.search(r"\b(meter|metre|rhythm|syllable|scansion)\b", lower) and re.search(
        r"\b(song|lyrics|verse|chorus|line|sing|rap)\b", lower
    ):
        return (
            "Meter tip: pick a time signature (4/4 is default), stress beat 1 and 3, keep line lengths even bar-to-bar. "
            "Read lines aloud and tap your foot — if a word lands late, swap a shorter synonym. "
            "Note the feel (straight vs swing) in Songs → notes ($0)."
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
    if "nashville" in lower or "number system" in lower:
        return (
            "Nashville numbers: in major, 1=tonic, 4=subdominant, 5=dominant, 6=relative minor — same shapes in any key. "
            "Write 1-5-6-4 instead of C-G-Am-F when jamming with the band. "
            "Note the key + numbers in Songs → chords so Bob and Logic stay aligned ($0)."
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
    norm = re.sub(r"[-_]", " ", lower)
    if "double chorus" in norm or "post chorus" in norm:
        return (
            "Double chorus: play the full chorus twice back-to-back; lift drums or harmony on the second pass. "
            "A post-chorus sits right after the chorus — hook riff or repeated lyric before the next verse. "
            "Note the map in Songs → notes; Logic arrangement is confirm-first."
        )
    if "tag line" in lower or "tagline" in norm or ("chorus" in lower and "tag" in lower):
        return (
            "Tag line: repeat one hook phrase after the chorus (often the title), same melody as the chorus hook. "
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
    if re.search(r"\bdeceptive\b|\bv\s*[-–→>]+\s*vi\b", lower):
        return (
            "Deceptive cadence: land on vi (relative minor) instead of I after V — feels unresolved, then resolve to I on the next bar. "
            "Try V–vi–IV–I or V–vi–V–I in the verse; save the map in Songs → chords ($0). "
            "Logic chord track is confirm-first."
        )
    if re.search(r"\bhalf\s*cadence\b|\bphrygian\s*half\b|\bv\s*[-–→>]+\s*v\b", lower):
        return (
            "Half cadence: pause on V (dominant) — sounds like a question before the chorus lands on I. "
            "Try ii–V at a section break, or V alone before the hook ($0). "
            "Mark the hit in Songs → chords; Logic tempo map is confirm-first."
        )
    if "chord" in lower or "progression" in lower:
        return (
            "For chords, try a simple loop (verse: I–V–vi–IV, chorus lift to IV or vi). "
            "Match the mood in the Songs tab — save a version after each pass. "
            "Local sketch demo ($0) can render a rough MP3 from lyrics + style when you are ready."
        )
    if "verse" in lower and "chorus" not in lower and "bridge" not in lower:
        return (
            "Verse polish: one image per line, end lines on unstressed syllables so the chorus hits harder. "
            "Keep rhyme loose until the hook — save each draft in Songs → versions ($0). "
            "If a line feels crowded, cut a word and let the refrain carry the title."
        )
    if "refrain" in lower and "chorus" not in lower and "hook" not in lower:
        return (
            "Refrain polish: keep it to one repeatable line (often the title) with the same rhythm each time. "
            "Trim extra syllables on beat 1; if the verse is wordy, make the refrain the emotional release. "
            "Save each pass in Songs → versions so Bob sees what changed ($0)."
        )
    coach_intent = re.search(
        r"\b(?:tip|tips|advice|coach|help|polish|tighten|sharpen|ideas?|how\s+should)\b",
        lower,
    )
    if "hook" in lower and "chorus" not in lower and "refrain" not in lower and coach_intent:
        return (
            "Hook polish: one singable phrase (3–7 syllables) that names the feeling, not the plot. "
            "Repeat it in the chorus and tag the last line of the verse with the same rhythm ($0). "
            "Save hook drafts in Songs → versions so Bob picks up the winner."
        )
    if "chorus" in lower or "hook" in lower or "refrain" in lower:
        return (
            "Chorus/refrain tip: one clear emotional line, repeat the title, keep lines short for singing. "
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
    if "bridge" in lower and "verse" not in lower and "chorus" not in lower and "structure" not in lower and coach_intent:
        return (
            "Bridge polish: one new image or question — change key or rhythm for 8 bars, then land on the chorus hook. "
            "Cut any line that repeats the verse; save the bridge as its own Songs version ($0)."
        )
    if re.search(r"\bababcb\b", lower) or "song form" in lower:
        return (
            "ABABCB form: A = verse, B = chorus, C = bridge — classic pop (e.g. verse–chorus–verse–chorus–bridge–chorus). "
            "Keep sections to 8 bars in 4/4; label A/B/C in Songs → notes so versions and Bob handback stay clear ($0)."
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

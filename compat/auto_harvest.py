#!/usr/bin/env python3
"""auto_harvest.py — promote research closeouts into next-prompts (architecture).

Called by ops-queue-refill on REAP_DONE. Stops the "queue empties until a human
self-improve run harvests NEXT_*.md by hand" metronome.

Rules:
  1. Always copy known deliverables into next-prompts/_inbox/ (timestamped).
  2. If job_dir/queue-ready/*.md exists, append each as a new READY INDEX row
     (next free Pri). Prefer WebJam filenames. Never invent content.
  3. If PROMOTE.json exists: [{"file":"15-….md","project":"WebJam","kind":"non-coding","notes":"..."}]
     with matching files under queue-ready/ or job root — same append.
  4. Exit 0 even when nothing to promote (harvest-only is success).
"""
from __future__ import annotations

import json
import os
import hashlib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("BOB_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "conductor/services"))
from state import atomic_write, job_event, lock
from jobs import closeout
NP = ROOT / "next-prompts"
INDEX = NP / "INDEX.md"
INBOX = NP / "_inbox"
DELIVERABLES = (
    "NEXT_PROMPTS.md",
    "NEXT_UX.md",
    "SUMMARY.md",
    "RESEARCH.md",
    "TEST_PLAN.md",
    "CHIP_MODULE_PLAN.md",
    "CI_STATUS.txt",
    "UX_LOGIC.md",
    "RESULT.txt",
    "RESULT.md",
    "BLOCKER.txt",
    "AUDIT.md",
    "SLICE_PLAN.md",
    "RESEARCH2.md",
)


def inbox_copy(job_dir: Path, job: str) -> list[str]:
    INBOX.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    copied = []
    for name in DELIVERABLES:
        src = job_dir / name
        if not src.is_file() or src.stat().st_size == 0:
            continue
        stem = Path(name).stem
        digest = hashlib.sha256(src.read_bytes()).hexdigest()[:16]
        dst = INBOX / f"{job}-{stem}-{digest}{src.suffix}"
        if not dst.exists():
            atomic_write(dst, src.read_text(encoding="utf-8", errors="replace"))
        copied.append(dst.name)
    return copied


def next_pri(text: str) -> int:
    pris = []
    for line in text.splitlines():
        if not line.strip().startswith("|") or re.search(r"\|\s*-+\s*\|", line):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if cols and cols[0].isdigit():
            pris.append(int(cols[0]))
    return (max(pris) + 1) if pris else 1


def append_ready(file_name: str, project: str, kind: str, notes: str, body: str) -> int:
    """Write prompt file + INDEX READY row. Returns pri."""
    text = INDEX.read_text(encoding="utf-8")
    marker = re.search(r"\[harvest:[^\]]+\]", notes)
    for line in text.splitlines():
        cols = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(cols) < 6 or not cols[0].isdigit():
            continue
        existing = NP / cols[1].strip("`")
        if (marker and marker.group(0) in line) or (existing.is_file() and existing.read_text().strip() == body.strip()):
            return int(cols[0])
    pri = next_pri(text)
    # Normalize filename to NN-slug.md
    slug = re.sub(r"^\d+-?", "", Path(file_name).stem)
    slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")[:48] or "harvested"
    out_name = f"{pri:02d}-{slug}.md"
    out_path = NP / out_name
    if not out_path.is_file():
        atomic_write(out_path, body if body.endswith("\n") else body + "\n")
    row = (
        f"| {pri} | `{out_name}` | {project} | {kind} | READY | "
        f"{notes} |\n"
    )
    if out_name in text and f"| {pri} |" in text:
        return pri
    # Append after last table row (before trailing sources blurb if any)
    lines = text.splitlines(keepends=True)
    last_table = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and not re.search(r"\|\s*-+\s*\|", line.strip()):
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if cols and cols[0].isdigit():
                last_table = i
    if last_table >= 0:
        lines.insert(last_table + 1, row)
    else:
        lines.append(row)
    atomic_write(INDEX, "".join(lines))
    return pri


def promote_from_queue_ready(job_dir: Path, job: str) -> list[str]:
    actions = []
    qr = job_dir / "queue-ready"
    promote_path = job_dir / "PROMOTE.json"
    items = []
    if promote_path.is_file():
        try:
            items = json.loads(promote_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ValueError(f"PROMOTE_JSON_BAD job={job}") from e
    if qr.is_dir():
        for p in sorted(qr.glob("*.md")):
            # skip if already listed in PROMOTE.json by file name
            if any(Path(str(it.get("file", ""))).name == p.name for it in items if isinstance(it, dict)):
                continue
            project = "WebJam" if "webjam" in p.name.lower() or "webjam" in job.lower() else "harvest"
            kind = "coding" if re.search(r"(test|fix|implement|coding)", p.name, re.I) else "non-coding"
            if "non-coding" in p.name.lower() or "audit" in p.name.lower() or "plan" in p.name.lower():
                kind = "non-coding"
            items.append(
                {
                    "file": p.name,
                    "project": project if project != "harvest" else ("WebJam" if "webjam" in job.lower() else "StoryBoard"),
                    "kind": kind,
                    "notes": f"auto-harvest from {job}",
                    "body_path": str(p),
                }
            )
    # Apply PROMOTE.json entries (body from queue-ready or job root)
    for it in items:
        if not isinstance(it, dict):
            continue
        fname = Path(str(it.get("file", ""))).name
        if not fname.endswith(".md"):
            continue
        body_path = Path(it.get("body_path") or "")
        if not body_path.is_file():
            for cand in (qr / fname, job_dir / fname, NP / fname):
                if cand.is_file():
                    body_path = cand
                    break
        if not body_path.is_file():
            raise ValueError(f"PROMOTE_MISS file={fname} job={job}")
        body = body_path.read_text(encoding="utf-8")
        if len(body.strip()) < 40:
            actions.append(f"PROMOTE_SKIP_SHORT file={fname}")
            continue
        project = str(it.get("project") or "WebJam")
        kind = str(it.get("kind") or "non-coding")
        notes = str(it.get("notes") or f"auto-harvest from {job}")
        marker = hashlib.sha256((fname + "\n" + body).encode()).hexdigest()[:16]
        notes += f" [harvest:{job}:{marker}]"
        pri = append_ready(fname, project, kind, notes, body)
        actions.append(f"PROMOTE_READY pri={pri} file={fname} kind={kind}")
    return actions


def _harvest_job(job: str) -> list[str]:
    job_dir = ROOT / job
    if not job_dir.is_dir():
        return [f"HARVEST_NO_DIR job={job}"]
    actions = []
    copied = inbox_copy(job_dir, job)
    if copied:
        actions.append(f"INBOX job={job} n={len(copied)} files={copied[:6]}")
    actions.extend(promote_from_queue_ready(job_dir, job))
    result = closeout(job_dir)
    blocker = job_dir / "BLOCKER.txt"
    if not result and blocker.is_file() and blocker.stat().st_size:
        result = blocker
    if result:
        job_event(job, "blocked" if result.name == "BLOCKER.txt" else "harvested", job_dir=str(job_dir), result_path=str(result),
                  result_sha256=hashlib.sha256(result.read_bytes()).hexdigest(),
                  outcome="blocked" if result.name == "BLOCKER.txt" else "result", recovery="harvest_complete")
    if len(actions) == 0:
        actions.append(f"HARVEST_EMPTY job={job} (no deliverables / queue-ready)")
    return actions


def harvest_job(job: str) -> list[str]:
    with lock("harvest"):
        return _harvest_job(job)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: auto_harvest.py <job-dir-name> [...]", file=sys.stderr)
        return 3
    all_actions = []
    for job in sys.argv[1:]:
        acts = harvest_job(job)
        for a in acts:
            print(f"HARVEST: {a}")
        all_actions.extend(acts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

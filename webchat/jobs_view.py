"""Small, read-only Jobs view. Dashboard, handback and round reports are not inputs."""
from __future__ import annotations

import math
import re
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

from live_status_snapshot import _job_bucket, _latest_jobs, _read_jsonl, observe_work, provider_health
from worker_activity import WORKER_NAMES

PROJECTS = ((r"web\s*bob|bob-brain", "Web Bob"), (r"web\s*jam", "WebJam"),
            (r"adopt\s*iq", "AdoptIQ"), (r"story\s*board|\bsb\b", "StoryBoard"), (r"\bshelf\b", "Shelf"))


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def plain(value, limit=140):
    text = str(value or "").splitlines()[0] if value else ""
    text = re.sub(r"\b[0-9a-f]{7,64}\b|\b(?:round\s*\d+|r\d+(?:-\d+)?)\b", "", text, flags=re.I)
    text = re.sub(r"[`*#]|https?://\S+|/(?:Users|home|tmp)/\S+", "", text)
    return " ".join(text.split()).strip(" ·:—-")[:limit]


def is_drill(record):
    return bool(record.get("fixture") or any(re.search(r"\b(?:handback|ready) drill\b|\bdrill-[\w-]+", str(record.get(key) or ""), re.I)
                                            for key in ("job_id", "id", "screen", "title")))


def labels(record, work=None):
    work = work or {}
    slug = work.get("screen") or record.get("job_id") or ""
    # Queue titles and an explicit Project line take precedence over lane names.
    project_line = re.search(r"(?m)^Project:\s*([^\n]+)", record.get("prompt") or "")
    candidates = [record.get("project"), project_line[1] if project_line else None,
                  record.get("title"), record.get("repo"), work.get("title"), slug]
    project = next((name for value in candidates if value for pattern, name in PROJECTS
                    if re.search(pattern, str(value).replace("_", " "), re.I)), None)
    project = project or plain(record.get("project"), 60) or "Project not specified"
    title = plain(record.get("title"))
    if not title and not work.get("screen") and work.get("title") != "Task details unavailable":
        title = plain(work.get("title"))
    if not title or title.lower() == project.lower():
        prompt = record.get("prompt") or ""
        if project_line:
            prompt = prompt[project_line.end():].lstrip()
        title = plain(prompt)
    if not title and slug and not slug.startswith("webchat-"):
        title = re.sub(r"^(?:lane|codex|claude|cursor|gemini|minimax)-", "", slug)
        title = re.sub(r"-\d{3,}$", "", title).replace("-", " ").replace("_", " ")
        for pattern, _ in PROJECTS:
            title = re.sub(pattern, "", title, flags=re.I)
        title = re.sub(r"\bclean\d*\b", "chat cleanup", title, flags=re.I)
        title = re.sub(r"\bui\b", "interface updates", title, flags=re.I)
        title = re.sub(r"\bci\b", "build checks", title, flags=re.I)
        title = plain(title)
        title = title[:1].upper() + title[1:] if title else ""
    if not title or title.lower() == project.lower():
        title = {"coding": "Updating the project", "analysis": "Reviewing the task",
                 "inspection": "Checking the project", "local": "Running checks",
                 "artifact": "Preparing a file"}.get(record.get("kind"), "Task details unavailable")
    return dict(project=project, task=title[:1].upper() + title[1:])


def safe_url(value):
    if not isinstance(value, str) or re.search(r"[\s\x00-\x1f]", value):
        return None
    try:
        url = urlsplit(value)
        if url.scheme in ("http", "https") and url.hostname and not url.username and not url.password:
            return value
    except ValueError:
        pass
    return None


def result_file(root, record):
    value = record.get("result_path")
    if not value:
        return None
    try:
        path = (root / str(value)).resolve()
        if path.is_relative_to(root.resolve()) and path.suffix.lower() in (".md", ".txt") and path.is_file():
            return path
    except (OSError, ValueError):
        pass
    return None


def result_text(root, identifier):
    record = _latest_jobs(root).get(identifier)
    if not record or is_drill(record) or _job_bucket(record) not in ("done", "failed", "cancelled", "canceled"):
        return None
    text = record.get("result") or (record.get("error") or record.get("recovery") if _job_bucket(record) == "failed" else None)
    path = result_file(root, record)
    if path:
        try:
            with path.open(errors="replace") as handle:
                text = handle.read(160000)
        except OSError:
            pass
    if not text:
        return None
    return dict(**labels(record), text=str(text)[:160000])


def age(root, relative, now):
    try:
        return round(max(0, now - (root / relative).stat().st_mtime))
    except OSError:
        return None


def costs(root):
    result = []
    for lane in ("gemini", "minimax"):
        path = root / "conductor/ledger" / (lane + ".jsonl")
        if not path.is_file():
            continue
        calls = {row["call_id"]: row for row in _read_jsonl(path) if row.get("call_id")}
        spent = sum(number(row.get("cost_usd")) or 0 for row in calls.values())
        reserved = sum(number(row.get("reserved_usd")) or 0 for row in calls.values() if row.get("cost_usd") is None)
        result.append(dict(provider=WORKER_NAMES[lane], spent_usd=round(spent, 4), reserved_usd=round(reserved, 4)))
    return result


def build_jobs_view(root: Path, *, now=None):
    now = time.time() if now is None else now
    observed = observe_work(root, now=now)
    records = {key: row for key, row in observed["records"].items() if not is_drill(row)}
    grouped = {}
    unconfirmed = 0
    for work in observed["work"]:
        if is_drill(work) or (work.get("job_id") and work["job_id"] not in records):
            continue
        if work["state"] == "claimed":
            unconfirmed += 1
            # A cached claim is not evidence of a running worker.
            if not work.get("screen", "") or not work["screen"].startswith("lane-"):
                continue
        key = work.get("screen") or work.get("job_id") or str(work.get("pid"))
        grouped.setdefault(key, []).append(work)
    working = []
    for key, group in grouped.items():
        work = next((row for row in group if row["state"] == "running"), group[0])
        record = records.get(work.get("job_id"), {})
        models = []
        for row in group:
            worker = WORKER_NAMES.get(row.get("worker"))
            model = plain(row.get("model"), 80)
            label = f"{worker} · {model}" if worker and model else worker or "Model not reported"
            if label not in models:
                models.append(label)
        durations = [row["elapsed_seconds"] for row in group if number(row.get("elapsed_seconds")) is not None]
        working.append(dict(key=key, **labels(record, work), models=models, state=work["state"],
                            elapsed_seconds=round(max(durations)) if durations else None))
    working.sort(key=lambda row: (row["state"] != "running", row["project"] == "Project not specified", row["project"], row["task"], row["key"]))
    finished = [row for row in records.values() if _job_bucket(row) in ("done", "failed", "cancelled", "canceled")]
    finished.sort(key=lambda row: number(row.get("finished_at")) or number(row.get("updated_at")) or number(row.get("timestamp")) or 0,
                  reverse=True)
    recent = []
    for record in finished[:5]:
        has_result = bool(record.get("result") or result_file(root, record) or
                          (_job_bucket(record) == "failed" and (record.get("error") or record.get("recovery"))))
        recent.append(dict(key=record["job_id"], **labels(record), state=_job_bucket(record),
                           finished_at=record.get("finished_at") or record.get("updated_at") or record.get("timestamp"),
                           result_url="/api/jobs/result?id=" + quote(record["job_id"], safe="") if has_result else None,
                           pr_url=safe_url(record.get("replacement_pr_url")) or safe_url(record.get("pr_url")),
                           external_result_url=safe_url(record.get("result_url"))))
    health = provider_health(root, now)
    return dict(checked_at=now, inspection=observed["inspection"], working=working, recently_finished=recent,
                details=dict(queued=sum(_job_bucket(row) == "queued" for row in records.values()),
                             unconfirmed=unconfirmed, costs=costs(root),
                             health=[dict(provider=WORKER_NAMES[name], state=row["state"],
                                          age_seconds=round(max(0, now - row["checked_at"])) if row.get("checked_at") else None)
                                     for name, row in health.items()],
                             sources=[dict(label="Queue", age_seconds=age(root, "conductor/state/queue.jsonl", now)),
                                      dict(label="Job history", age_seconds=age(root, "conductor/jobs.jsonl", now)),
                                      dict(label="Provider health", age_seconds=age(root, "conductor/webchat/sessions/provider-health.json", now))]))

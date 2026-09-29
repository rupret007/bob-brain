"""Small, read-only Jobs view. Dashboard, handback and round reports are not inputs."""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

from lane_collector import collect_bob_lanes
from live_status_snapshot import _job_bucket, _latest_jobs, observe_work, provider_health
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
    screen = work.get("screen")
    task_screen = screen if screen and screen != "svc-job-runner" else None
    slug = task_screen or record.get("job_id") or ""
    # Queue titles and an explicit Project line take precedence over lane names.
    project_line = re.search(r"(?m)^Project:\s*([^\n]+)", record.get("prompt") or "")
    candidates = [record.get("project"), project_line[1] if project_line else None,
                  record.get("title"), record.get("repo"), work.get("title"), slug]
    project = next((name for value in candidates if value for pattern, name in PROJECTS
                    if re.search(pattern, str(value).replace("_", " "), re.I)), None)
    project = project or plain(record.get("project"), 60) or "Project not specified"
    title = plain(record.get("title"))
    if not title and not task_screen and work.get("title") != "Task details unavailable":
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
        title = re.sub(r"^svc\s+", "", title, flags=re.I)
        title = {"reviewers": "Reviewing changes", "voice": "Voice updates"}.get(title.strip().lower(), title)
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
        try:
            calls = {row["call_id"]: row for row in (json.loads(line) for line in path.read_text().splitlines() if line.strip())}
            spent, reserved = 0, 0
            for row in calls.values():
                cost = row.get("cost_usd")
                value = number(cost if cost is not None else row.get("reserved_usd"))
                if value is None or value < 0:
                    raise ValueError("Unknown cost")
                if cost is None:
                    reserved += value
                else:
                    spent += value
            result.append(dict(provider=WORKER_NAMES[lane], spent_usd=round(spent, 4) if calls else None,
                               reserved_usd=round(reserved, 4) if calls else None))
        except (OSError, ValueError, KeyError, TypeError):
            result.append(dict(provider=WORKER_NAMES[lane], spent_usd=None, reserved_usd=None))
    return result


def _lane_model_label(lane: dict) -> str:
    worker = WORKER_NAMES.get(lane.get("llm")) or lane.get("llm_label") or "Model not reported"
    model = plain(lane.get("model"), 80)
    return f"{worker} · {model}" if model else worker


def _lane_card(lane: dict) -> dict:
    project = plain(lane.get("project"), 60) or "Project not specified"
    task = plain(lane.get("task")) or plain(lane.get("screen", "").removeprefix("lane-").replace("-", " "))
    task = task[:1].upper() + task[1:] if task else "Task details unavailable"
    models = [_lane_model_label(lane)]
    card = dict(
        key=lane["screen"],
        project=project,
        task=task,
        models=models,
        state=lane.get("state") or "unverified",
        elapsed_seconds=number(lane.get("elapsed_seconds")),
        lane=True,
    )
    if lane.get("result_path"):
        card["external_result_url"] = "/" + lane["result_path"]
    return card


def build_jobs_view(root: Path, *, now=None):
    now = time.time() if now is None else now
    observed = observe_work(root, now=now)
    # One sample establishes both cards and inspection health. Retrying a
    # failed sample can otherwise invent a live lane while reporting failure.
    bob = collect_bob_lanes(root, now=now, observed=observed)
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
    lane_cards = {lane["screen"]: _lane_card(lane) for lane in (bob.get("live") or [])}
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
        card = lane_cards.get(key)
        if card:
            card = dict(card)
            if models:
                card["models"] = models
            card["state"] = work["state"]
            if durations:
                card["elapsed_seconds"] = round(max(durations))
            if card.get("task") == "Task details unavailable" or record.get("title"):
                card.update(labels(record, work))
            working.append(card)
        else:
            working.append(dict(key=key, **labels(record, work), models=models, state=work["state"],
                                elapsed_seconds=round(max(durations)) if durations else None))
    for key, card in lane_cards.items():
        if key not in grouped:
            working.append(card)
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
    for lane in bob.get("finished_recent") or []:
        recent.append(dict(
            key=lane["screen"],
            project=plain(lane.get("project"), 60) or "Project not specified",
            task=plain(lane.get("task")) or lane["screen"].removeprefix("lane-").replace("-", " "),
            state="done",
            finished_at=lane.get("finished_at"),
            external_result_url=("/" + lane["result_path"]) if lane.get("result_path") else None,
        ))
    recent.sort(key=lambda row: number(row.get("finished_at")) or 0, reverse=True)
    recent = recent[:5]
    health = provider_health(root, now)
    solo = (root / 'conductor/SOLO-WORKER').exists()
    paused = solo or (root / 'conductor/MAINTENANCE').exists()
    queued = sum(_job_bucket(row) == 'queued' for row in records.values())
    dispatch = dict(paused=paused, mode='solo' if solo else 'paused' if paused else 'enabled',
                    queued=queued if observed['inspection']['queue_available'] else None)
    return dict(checked_at=now, inspection=observed["inspection"], working=working, recently_finished=recent,
                dispatch=dispatch, dispatch_paused=paused,
                details=dict(queued=sum(_job_bucket(row) == "queued" for row in records.values()),
                             unconfirmed=unconfirmed, costs=costs(root),
                             health=[dict(provider=WORKER_NAMES[name], state=row["state"],
                                          age_seconds=round(max(0, now - row["checked_at"])) if row.get("checked_at") else None)
                                     for name, row in health.items()],
                             sources=[dict(label="Queue", age_seconds=age(root, "conductor/state/queue.jsonl", now)),
                                      dict(label="Job history", age_seconds=age(root, "conductor/jobs.jsonl", now)),
                                      dict(label="Provider health", age_seconds=age(root, "conductor/webchat/sessions/provider-health.json", now))]))

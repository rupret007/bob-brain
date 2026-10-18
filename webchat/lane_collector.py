"""Read-only collector for Bob overnight lane-* screen sessions on the mini."""
from __future__ import annotations

import re
import time
from pathlib import Path

from worker_activity import WORKER_NAMES, collect_work
from worker_evidence import _match_file, _project, _task, read_part

FINISHED_WINDOW_SECONDS = 12 * 3600
_LLM_LABEL = {
    "codex": "Codex",
    "claude": "Claude",
    "cursor": "cursor-agent",
    "gemini": "gemini",
    "minimax": "minimax",
}


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z]+|\d+", value.lower())


def prompt_slug(stem: str) -> str:
    """Map logs/foo-bar-2005-prompt.txt stem to lane-foo-bar-2005 (trim date suffixes)."""
    name = re.sub(r"-prompt$", "", stem, flags=re.I)
    name = re.sub(r"-\d{4}$", "", name)
    return "lane-" + name


def screen_slug(screen: str) -> str:
    return re.sub(r"^(?:lane|svc)-", "", screen or "")


def _review_from_prompt(prompt: str, root: Path) -> Path | None:
    match = re.search(r"reviews/([\w./-]+\.md)", prompt or "", re.I)
    if not match:
        return None
    path = (root / "reviews" / Path(match.group(1)).name).resolve()
    try:
        if path.is_file() and path.is_relative_to(root.resolve()):
            return path
    except (OSError, ValueError):
        pass
    return None


def _review_guess(root: Path, screen: str | None, prompt: str) -> Path | None:
    explicit = _review_from_prompt(prompt, root)
    if explicit:
        return explicit
    words = _tokens(screen_slug(screen or ""))
    if not words:
        return None
    candidates: list[tuple[float, Path]] = []
    folder = root / "reviews"
    if not folder.is_dir():
        return None
    for path in folder.glob("*.md"):
        if path.is_symlink():
            continue
        tokens = _tokens(path.stem)
        if not all(word in tokens for word in words):
            continue
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue
    return max(candidates)[1] if candidates else None


def _log_path(root: Path, screen: str, command: str, logs: list[Path]) -> Path:
    matched = _match_file(root, logs, screen, command)
    if matched:
        return matched
    slug = screen_slug(screen)
    folder = root / "logs"
    candidates: list[tuple[float, Path]] = []
    for path in folder.glob(slug + "*.log"):
        if "prompt" in path.name.lower():
            continue
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue
    if candidates:
        return max(candidates)[1]
    return root / "logs" / (screen + ".log")


def _prompt_path(root: Path, screen: str, command: str, prompts: list[Path]) -> Path | None:
    matched = _match_file(root, prompts, screen, command)
    if matched:
        return matched
    slug = screen_slug(screen)
    folder = root / "logs"
    candidates: list[tuple[float, Path]] = []
    for path in folder.glob("*prompt*.txt"):
        tokens = _tokens(path.stem)
        slug_tokens = _tokens(slug)
        if slug_tokens and all(word in tokens for word in slug_tokens):
            try:
                candidates.append((path.stat().st_mtime, path))
            except OSError:
                continue
    return max(candidates)[1] if candidates else None


def _llm_label(worker: str | None) -> str | None:
    if not worker:
        return None
    if worker in _LLM_LABEL:
        return _LLM_LABEL[worker]
    return WORKER_NAMES.get(worker, worker)


def _lane_record(root: Path, screen: str, work_row: dict | None, *, prompts, logs, now: float, finished: bool) -> dict:
    root = Path(root).resolve()
    command = ""
    if work_row and work_row.get("pid"):
        command = work_row.get("command", "")
    prompt_path = work_row.get("prompt_path") if work_row else None
    path_obj = root / prompt_path if prompt_path else _prompt_path(root, screen, command, prompts)
    prompt = read_part(path_obj) if path_obj and path_obj.is_file() else ""
    log_path = work_row.get("log_path") if work_row else None
    log_obj = root / log_path if log_path else _log_path(root, screen, command, logs)
    review = _review_guess(root, screen, prompt)
    project, repo = _project(prompt[:2000] or (work_row or {}).get("title", ""))
    if not project and work_row:
        project, repo = work_row.get("project"), work_row.get("repo")
    task = _task(prompt) or (work_row or {}).get("task") or (work_row or {}).get("title")
    worker = (work_row or {}).get("worker")
    model = (work_row or {}).get("model")
    elapsed = (work_row or {}).get("elapsed_seconds")
    state = (work_row or {}).get("state") or ("finished" if finished else "unverified")
    ended_at = None
    if finished:
        stamps = []
        for path in (path_obj, log_obj, review):
            if path and Path(path).is_file():
                try:
                    stamps.append(Path(path).stat().st_mtime)
                except OSError:
                    pass
        ended_at = max(stamps) if stamps else None
        if ended_at is not None:
            elapsed = max(0, int(now - ended_at))
    rel_review = None
    if review:
        try:
            rel_review = str(review.resolve().relative_to(root))
        except ValueError:
            rel_review = None
    pid = (work_row or {}).get("pid")
    last_log = (work_row or {}).get("last_log_line")
    return dict(
        screen=screen,
        pid=pid,
        llm=worker,
        llm_label=_llm_label(worker),
        model=model,
        project=project,
        repo=repo,
        task=task,
        state='not_observed' if finished else state,
        elapsed_seconds=elapsed,
        finished_at=None,
        last_activity_at=ended_at,
        prompt_path=str(path_obj.relative_to(root)) if path_obj and path_obj.is_file() else None,
        log_path=str(log_obj.relative_to(root)) if log_obj else None,
        result_path=rel_review,
        last_log_line=last_log,
        source="lane_collector",
    )


def collect_bob_lanes(
    root: Path,
    *,
    now: float | None = None,
    sessions: dict[str, str] | None = None,
    processes: dict | None = None,
    observed: dict | None = None,
    finished_window: float = FINISHED_WINDOW_SECONDS,
) -> dict:
    """Parse lane-* screens and ps, map prompts/logs/reviews; include recent finished lanes."""
    from live_status_snapshot import _queue_jobs, _screen_sessions, read_job_journals

    root = Path(root).resolve()
    now = time.time() if now is None else now
    if observed is not None:
        # A status reply and its lane details must share one worker sample,
        # including failed inspections; never retry into a different state.
        sessions_map, work = observed["sessions"], observed["work"]
        inspection = {key: observed["inspection"][key] for key in ("screens_available", "processes_available")}
    else:
        screen_sample = sessions if sessions is not None else _screen_sessions(root)
        sessions_map = screen_sample or {}
        if processes is None:
            from worker_activity import process_table

            processes = process_table(root)
        jobs_map, _ = read_job_journals(root)
        claimed = _queue_jobs(jobs_map, set(sessions_map))["claimed"]
        work = collect_work(sessions_map, claimed, processes, now, root=root)
        inspection = dict(screens_available=screen_sample is not None, processes_available=processes is not None)
    work_by_screen = {row["screen"]: row for row in work if (row.get("screen") or "").startswith("lane-")}
    prompts = list((root / "logs").glob("*prompt*.txt"))
    logs = [path for path in (root / "logs").glob("*.log") if "prompt" not in path.name.lower()]
    live_screens = sorted(name for name in sessions_map if name.startswith("lane-"))
    live = [_lane_record(root, screen, work_by_screen.get(screen), prompts=prompts, logs=logs, now=now, finished=False)
            for screen in live_screens]
    active = set(live_screens)
    finished_recent: list[dict] = []
    for prompt_path in prompts:
        if not inspection['screens_available']:
            break  # A failed screen inspection cannot establish that a lane ended.
        screen = prompt_slug(prompt_path.stem)
        if screen in active:
            continue
        prompt = read_part(prompt_path)
        review = _review_guess(root, screen, prompt)
        stamps = [prompt_path.stat().st_mtime]
        log_guess = _log_path(root, screen, "", logs)
        if log_guess.is_file():
            try:
                stamps.append(log_guess.stat().st_mtime)
            except OSError:
                pass
        if review:
            try:
                stamps.append(review.stat().st_mtime)
            except OSError:
                pass
        ended_at = max(stamps) if stamps else None
        if ended_at is None or now - ended_at > finished_window:
            continue
        project, repo = _project(prompt)
        finished_recent.append(
            _lane_record(
                root,
                screen,
                dict(
                    state="finished",
                    project=project,
                    repo=repo,
                    task=_task(prompt),
                    prompt_path=str(prompt_path.relative_to(root)),
                    log_path=str(log_guess.relative_to(root)) if log_guess.is_file() else None,
                ),
                prompts=prompts,
                logs=logs,
                now=now,
                finished=True,
            )
        )
    finished_recent.sort(key=lambda row: row.get("last_activity_at") or 0, reverse=True)
    return dict(
        captured_at=now,
        inspection=inspection,
        live=live,
        finished_recent=finished_recent,
    )

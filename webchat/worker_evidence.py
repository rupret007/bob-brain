"""Bounded, read-only task evidence for live processes and screen lanes."""
import re
from pathlib import Path

PROJECTS = ((r"web\s*bob|conductor", "Web Bob", "conductor"),
            (r"web\s*jam", "WebJam", "webjam"), (r"adopt\s*iq", "AdoptIQ", "AdoptIQ"),
            (r"story\s*board", "StoryBoard", "StoryBoard"),
            (r"(?:storyland[ -])?fantasy[ -]football|fantasy", "Fantasy Football", "Storyland-Fantasy-Football"),
            (r"shelf", "Shelf", "story-corner-shelf"))


def clean(text, limit=220):
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\b(?:sk-[\w-]{20,}|AIza[\w-]{25,}|gh[pousr]_[\w]{25,})\b", "[secret removed]", text)
    text = re.sub(r"(?i)\b(?:password|token|secret|api_key)\s*[:=]\s*\S+", "[secret removed]", text)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    # Never end mid-word: a truncated raw log line should read as a phrase,
    # not garbage cut off between letters.
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped


def read_part(path, tail=False):
    # Prompt/log discovery never follows a link into credentials or another tree.
    if path.is_symlink() or not path.is_file():
        return ""
    try:
        with path.open("rb") as handle:
            if tail:
                handle.seek(0, 2)
                handle.seek(max(0, handle.tell() - 8192))
            return handle.read(8192).decode("utf-8", "replace")
    except OSError:
        return ""


def _tokens(value):
    return re.findall(r"[a-z]+|\d+", value.lower())


def _match_file(root, paths, screen, command):
    words = _tokens(re.sub(r"^(?:lane|svc)-", "", screen or ""))
    candidates = []
    for path in paths:
        tokens = _tokens(path.stem)
        # Explicit paths beat filename heuristics; all screen words must match.
        explicit = str(path) in command or str(path.relative_to(root)) in command
        matched = bool(words) and all(word in tokens for word in words)
        if not explicit and not matched:
            continue
        try:
            candidates.append(((int(explicit), len(words), path.stat().st_mtime), path))
        except OSError:
            continue
    return max(candidates)[1] if candidates else None


def _project(text):
    matches = [(match.start(), project, repo) for pattern, project, repo in PROJECTS
               if (match := re.search(r"\b(?:" + pattern + r")\b", text, re.I))]
    return min(matches)[1:] if matches else (None, None)


def _task(prompt):
    # Prefer the assignment to setup/rules or old quoted replies in the prompt.
    header = re.search(r"(?im)^\s*(?:task|goal|assignment)\s*:\s*(.+)", prompt)
    text = header[1] if header else prompt.splitlines()[0] if prompt else ""
    text = re.sub(r"^(?:TOP PRIORITY[.!:]?\s*)", "", text, flags=re.I)
    if re.match(r"Follow-up \d+ on [\w./-]+:", text):
        text = re.sub(r"^Follow-up \d+ on [\w./-]+:\s*", "", text)
        text = re.split(r"[;(]", text, maxsplit=1)[0]
    text = re.sub(r"^Project:\s*[^\n]+", "", text, flags=re.I)
    if not text and prompt:
        text = next((line for line in prompt.splitlines()[1:] if line.strip()), "")
    text = re.split(r"[.!?]\s", text, maxsplit=1)[0]
    text = re.sub(r"\b[0-9a-f]{7,40}\b", "", text)
    if re.search(r"\b(?:read|review|audit|fix|repair|implement|build|improve|develop|test|redesign|replies|reply|status|check|plan|research|gives bad)\b", text, re.I):
        return clean(text, 160).strip(" .")
    return None


def _inline_prompt(command):
    """Only the live CLI's task argument, not strings in an arbitrary process."""
    command = command.replace("\\012", "\n")
    match = re.search(r"\s(?:-p|--print)\s+(.+)", command, re.S)
    if match:
        return match[1]
    match = re.search(r"\b(?:exec|review)\s+(.+)", command, re.S)
    if not match:
        return ""
    text = match[1]
    while text.startswith("-"):
        option = re.match(r"(--?[\w-]+)(?:=\S+)?\s*", text)
        if not option:
            return ""
        text = text[option.end():]
        if option[1] in ("-c", "--config", "-m", "--model", "-C", "--cd", "-s", "--sandbox", "-a", "--ask-for-approval", "-o", "--output-last-message"):
            text = re.sub(r"^(?:\"[^\"]*\"|'[^']*'|\S+)\s*", "", text)
    return text


def enrich_work(root, activity, records, table):
    root = Path(root)
    prompts = list((root / "logs").glob("*prompt*.txt"))
    logs = list((root / "logs").glob("*.log"))
    by_job = {row["job_id"]: row for row in records}
    for row in activity:
        record = by_job.get(row.get("job_id"), {})
        pid = row.get("pid")
        chain, seen = [], set()
        while pid in table and pid not in seen:
            seen.add(pid)
            chain.append(table[pid]["command"])
            pid = table[pid]["ppid"]
        command = "\n".join(chain)
        prompt_path = _match_file(root, prompts, row.get("screen"), command)
        log_path = _match_file(root, logs, row.get("screen"), command)
        if record:
            run_dir = root / "conductor/state/task-runs" / record["job_id"]
            if (run_dir / "prompt.txt").is_file():
                prompt_path = run_dir / "prompt.txt"
            log_path = log_path or run_dir / "worker.log"
        if log_path is None:
            log_path = root / "logs" / ((row.get("screen") or "process-" + str(row.get("pid", "observed"))) + ".log")
        prompt = record.get("prompt") or (read_part(prompt_path) if prompt_path else "")
        if not prompt and row.get("worker") in ("codex", "cursor", "claude"):
            prompt = _inline_prompt(table.get(row.get("pid"), {}).get("command", ""))
        # A casual reply quotes one short evidence line, not a run-on paragraph:
        # cap well under the 220-char default used for prose fields.
        tail = [clean(line, 120) for line in read_part(log_path, tail=True).splitlines() if line.strip()]
        last = tail[-1] if tail else "log has no readable lines"
        task = _task(prompt) or _task(record.get("title") or "")
        if not task and row["title"] != "Worker process" and not row.get("screen"):
            task = row["title"]
        if not task:
            task = next((_task(line) for line in reversed(tail)
                         if re.match(r"(?:Task:|Goal:|Working on |Reviewing |Fixing )", line, re.I) and _task(line)), None)
        # Resolve the project from the assignment, never from an unrelated log.
        project, repo = _project(record.get("project") or prompt[:1500] or row["title"])
        if not repo:
            project, repo = _project(row["title"])
        if not repo:
            cwd = re.search(r"\bcd\s+([^;&\n]+)", command)
            if cwd:
                project, repo = _project(cwd[1])
        explicit_repo = re.search(r"(?im)^\s*(?:repo|repository)\s*:\s*([^\n]+)", prompt)
        repo = Path(record["repo"]).name if record.get("repo") else repo
        if explicit_repo and not repo:
            repo = clean(explicit_repo[1], 100)
        row.update(project=project, repo=repo, task=task,
                   prompt_path=str(prompt_path.relative_to(root)) if prompt_path else None,
                   log_path=str(log_path.relative_to(root)), last_log_line=last)
        if task:
            row["title"] = task
    return activity

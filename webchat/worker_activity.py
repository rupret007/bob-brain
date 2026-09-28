"""Read-only worker discovery. Process commands stay private to this collector."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

WORKER_NAMES = {"codex": "Codex", "claude": "Claude", "cursor": "Cursor",
                "gemini": "Gemini", "minimax": "MiniMax", "mini": "mini"}


def elapsed_seconds(value):
    """ps etime is [[days-]hours:]minutes:seconds on macOS and Linux."""
    try:
        days, separator, clock = value.partition("-")
        seconds = 0
        for part in (clock if separator else days).split(":"):
            seconds = seconds * 60 + int(part)
        return seconds + (int(days) * 86400 if separator else 0)
    except (ValueError, AttributeError):
        return None


def process_table(root):
    try:
        result = subprocess.run(["/bin/ps", "-ww", "-axo", "pid=,ppid=,etime=,stat=,command="],
                                cwd=root, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    return parse_processes(result.stdout) or None


def parse_processes(output):
    rows = {}
    for line in output.splitlines():
        match = re.match(r"^\s*(\d+)\s+(\d+)\s+([\d:-]+)\s+(\S+)\s+(.+)$", line)
        if not match:
            continue
        pid, parent, elapsed, state, command = match.groups()
        rows[int(pid)] = dict(pid=int(pid), ppid=int(parent), elapsed_seconds=elapsed_seconds(elapsed),
                              process_state=state, command=command)
    return rows


def _identity(command):
    # Only the executable (or a known CLI script behind node) identifies a
    # worker. A shell, test or prompt mentioning "codex" is not a worker.
    parts = command.split()
    if not parts:
        return None, None
    # CLI names are case sensitive. Desktop Claude/Codex helpers (including
    # paths with spaces such as "Codex Framework.framework") are not workers.
    executable = Path(parts[0]).name
    if executable.lower().startswith("python") and len(parts) > 2:
        script = Path(parts[1]).name
        if script == "-c":
            api = re.search(r"\b(?:ask|model_call)\([\"'](gemini|minimax)[\"']", command)
            if api:
                return api[1], None
        if script in ("compat.py", "api_call.py", "llm_ask.py") and parts[2] in ("gemini", "minimax"):
            return parts[2], None
        if script in ("minimax-arch-review.py", "minimax_verdict.py", "gemini-arch-review.py", "gemini_tip_assess.py"):
            return script.split("-", 1)[0].split("_", 1)[0], None
    if executable in ("node", "nodejs") and len(parts) > 1:
        script = parts[1].lower()
        if "/@openai/codex/" in script and script.endswith("/codex.js"):
            executable = "codex"
        elif "/@anthropic-ai/claude-code/" in script and script.endswith("/cli.js"):
            executable = "claude"
        elif "/cursor-agent/" in script and script.endswith("/index.js"):
            executable = "cursor-agent"
        else:
            return None, None
        parts = parts[1:]
    worker = {"cursor-agent": "cursor"}.get(executable, executable)
    if worker not in ("codex", "claude", "cursor", "gemini") or executable == "cursor":
        return None, None
    # Desktop app-server/MCP/login processes are infrastructure, not jobs.
    if any(word in parts[1:4] for word in ("app-server", "mcp-server", "login", "logout", "status", "--help", "--version")):
        return None, None
    model = None
    execution = worker != "codex"
    # Stop at the task text; a --model example inside a prompt is not evidence.
    index = 1
    valued = {"-c", "--config", "-C", "--cd", "-s", "--sandbox", "-a", "--ask-for-approval",
              "--output-format", "--output-last-message", "-o", "--allowedTools", "--permission-mode"}
    while index < len(parts):
        token = parts[index]
        if token in ("-m", "--model") and index + 1 < len(parts):
            value = parts[index + 1].strip("\"'")
            if re.fullmatch(r"[\w./:-]{1,80}", value):
                model = value
            index += 2
        elif token.startswith("--model="):
            value = token.partition("=")[2].strip("\"'")
            if re.fullmatch(r"[\w./:-]{1,80}", value):
                model = value
            index += 1
        elif token in valued:
            index += 2
        elif token in ("exec", "review", "resume"):
            execution = True
            index += 1
        elif token.startswith("-") or token.endswith("/index.js"):
            index += 1
        else:
            break
    return (worker, model) if execution else (None, None)


def task_label(record=None, screen=None):
    record = record or {}
    title = record.get("title") or record.get("project")
    if title:
        return " ".join(str(title).split())[:100]
    if screen and screen.startswith("lane-"):
        label = screen.removeprefix("lane-").replace("-", " ").replace("_", " ")
        label = re.sub(r"(?<=[a-z])(?=\d)", " ", label)
        for raw, pretty in (("webbob", "Web Bob"), ("webjam", "WebJam"), ("adoptiq", "AdoptIQ"),
                            ("storyboard", "StoryBoard"), ("minimax", "MiniMax")):
            label = re.sub(r"\b" + raw + r"\b", pretty, label, flags=re.I)
        return label[:1].upper() + label[1:100]
    return "Worker process"


def task_header(command):
    """Recognize an explicit assignment header, never expose the whole prompt."""
    match = re.search(r"\bFollow-up \d+ on [\w./-]+:\s*([^\n]{1,500}?)(?:\.\s|\n|$)", command)
    if not match:
        return None
    title = re.split(r"[;(]", match[1], maxsplit=1)[0].replace("EVERY", "every")
    title = re.sub(r"/(?:Users|home|tmp)/\S+|\b[0-9a-f]{7,64}\b", "", title, flags=re.I)
    return " ".join(title.split()).strip(" .")[:140] or None


def collect_work(sessions, claimed_jobs, processes, now, root=None):
    """Join queue claims and live workers without counting a wrapper twice."""
    table = processes or {}
    screens = {int(value.split(".", 1)[0]): name for name, value in sessions.items()
               if value.split(".", 1)[0].isdigit()}

    def ancestry(pid):
        chain = []
        while pid in table and pid not in chain:
            chain.append(pid)
            pid = table[pid]["ppid"]
        return chain

    identities = {pid: _identity(row["command"]) for pid, row in table.items()
                  if not row["process_state"].startswith(("Z", "X"))}
    workers = {pid: value for pid, value in identities.items() if value[0]}
    # Native CLI children of node wrappers represent the same assignment.
    roots = [pid for pid in workers if not any(parent in workers for parent in ancestry(pid)[1:])]
    activity, matched_jobs, matched_screens = [], set(), set()
    for pid in roots:
        chain = ancestry(pid)
        screen = next((screens[parent] for parent in chain if parent in screens), None)
        record = next((row for row in claimed_jobs if row.get("pid") in chain
                       or (screen and row["job_id"] == screen)), None)
        worker, model = workers[pid]
        row = table[pid]
        descendants = [child for child in workers if pid in ancestry(child)]
        # Prefer explicit model metadata from the actual binary if a wrapper
        # has none. Never guess a model from a lane's name or cached lock.
        model = model or next((workers[child][1] for child in descendants if workers[child][1]), None)
        if record and worker in ("gemini", "minimax"):
            model = model or record.get("model")
        state = "paused" if any(table[child]["process_state"].startswith("T") for child in descendants) else "running"
        title = task_label(record, screen if screen and not screen.startswith("svc-") else None)
        if title == "Worker process":
            title = task_header(row["command"]) or title
        activity.append(dict(title=title,
                             worker=worker, model=model, state=state, elapsed_seconds=row["elapsed_seconds"],
                             pid=pid, screen=screen, job_id=record["job_id"] if record else None,
                             source="process"))
        if record:
            matched_jobs.add(record["job_id"])
        if screen:
            matched_screens.add(screen)
    for record in claimed_jobs:
        if record["job_id"] in matched_jobs:
            continue
        screen = record["job_id"] if record["job_id"] in sessions else None
        started = record.get("started_at") or record.get("claimed_at") or record.get("launched_at")
        process = table.get(record.get("pid")) or {}
        argv = process.get("command", "").split()
        # API/local workers may have no CLI child. Verify the dispatch process
        # and its task argument so a reused PID cannot establish live work.
        confirmed = (len(argv) >= 3 and Path(argv[1]).name in ("dispatch_worker.py", "worker.py")
                     and argv[2] == record["job_id"] and not process["process_state"].startswith(("Z", "X")))
        state = ("paused" if process["process_state"].startswith("T") else "running") if confirmed else "claimed"
        if confirmed:
            screen = next((screens[parent] for parent in ancestry(record["pid"]) if parent in screens), screen)
        activity.append(dict(title=task_label(record, screen), worker=record.get("worker"), model=record.get("model"),
                             state=state, elapsed_seconds=process["elapsed_seconds"] if confirmed else
                             max(0, now - started) if isinstance(started, (int, float)) else None,
                             pid=record.get("pid") if confirmed else None,
                             job_id=record["job_id"], screen=screen, source="process" if confirmed else "queue"))
        if screen:
            matched_screens.add(screen)
    for name in sessions:
        if name.startswith("lane-") and name not in matched_screens:
            # A shell/sleep or a missing process sample cannot establish work.
            screen_pid = int(sessions[name].split(".", 1)[0])
            activity.append(dict(title=task_label(screen=name), worker=None, model=None, state="unverified",
                                 elapsed_seconds=table.get(screen_pid, {}).get("elapsed_seconds"),
                                 screen=name, pid=screen_pid, source="screen"))
    if root is not None:
        from worker_evidence import enrich_work
        activity = enrich_work(root, activity, claimed_jobs, table)
        for row in activity:
            if row["title"] == "Worker process" and not row.get("task") and not row.get("job_id"):
                row.update(state="unverified", assignment_recorded=False,
                           title=WORKER_NAMES.get(row.get("worker"), "Worker") + " CLI activity")
    return activity

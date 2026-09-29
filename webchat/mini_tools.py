"""Explicit phone commands, executed locally with bounded output and no shell."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from providers import clean_env, run


def repositories(root):
    rows = {"conductor": root / "conductor", "webbob": root / "conductor"}
    config = root / "conductor/services/projects.json"
    if config.exists():
        for name, item in json.loads(config.read_text()).items():
            rows[name.lower()] = Path(item["repo"]).expanduser().resolve()
    return rows


def repository(root, name):
    rows = repositories(root)
    name = (name or "conductor").strip().strip("`")
    if name.lower() in rows:
        return rows[name.lower()]
    candidate = Path(name).expanduser().resolve()
    if candidate in rows.values():
        return candidate
    raise ValueError("Choose a configured repo: " + ", ".join(rows) + ".")


def parse_tool(text):
    match = re.fullmatch(r"(?:repo(?:sitory)? status|git status)(?:\s*:\s*(.+))?", text.strip(), re.I)
    if match:
        return {"kind": "repo", "value": match[1] or "conductor"}
    match = re.fullmatch(r"(?:run command|run on (?:the )?mini|run)\s*:\s*(.+)", text.strip(), re.I | re.S)
    if match:
        return {"kind": "command", "value": match[1]}
    match = re.fullmatch(r"(?:please )?run (pwd|hostname|uptime|whoami|date|uname -a|sw_vers|df -h|screen -ls)(?: on (?:the )?mini)?[.!]?", text.strip(), re.I)
    return {"kind": "command", "value": match[1]} if match else None


def command(root, raw):
    if re.search(r"[\n\r;|&<>`$]", raw):
        raise ValueError("Use one command without shell operators. For a larger task, say `start a job: …`.")
    argv = shlex.split(raw)
    fixed = {("pwd",), ("hostname",), ("uptime",), ("whoami",), ("date",),
             ("uname", "-a"), ("sw_vers",), ("df", "-h"), ("screen", "-ls")}
    cwd = root / "conductor"
    if tuple(argv) in fixed:
        return argv, cwd
    if argv and argv[0] == "git":
        args = argv[1:]
        if args[:1] == ["-C"] and len(args) >= 3:
            cwd = repository(root, args[1])
            args = args[2:]
        allowed = {("status",), ("status", "--short"), ("status", "--short", "--branch"),
                   ("status", "--porcelain"), ("branch", "--show-current"),
                   ("rev-parse", "HEAD"), ("rev-parse", "--short", "HEAD"),
                   ("log", "-5", "--oneline"), ("diff", "--stat"), ("diff", "--check")}
        if tuple(args) in allowed:
            return ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", *args], cwd
    raise ValueError("Quick commands: pwd, hostname, uptime, whoami, date, uname -a, sw_vers, df -h, screen -ls, and git status/log/diff --stat. For other work, say `start a job: …`.")


def execute(root, request, cancel, redact):
    try:
        if request["kind"] == "repo":
            cwd = repository(root, request["value"])
            argv = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "status", "--short", "--branch"]
        else:
            argv, cwd = command(root, request["value"])
        code, out, err = run(argv, cwd=cwd, env=clean_env(), cancel=cancel, timeout=15)
        output = redact((out + err).strip())
        if len(output) > 16000:
            output = output[:16000] + "\n[output truncated]"
        content = f"Ran on the mini in `{cwd}` (exit {code}):\n\n```\n{output or '(no output)'}\n```"
        state = "done" if code == 0 else "blocked"
    except ValueError as exc:
        content, state = str(exc), "refused"
    return {"content": content, "provider": "mini", "codex_thread_id": None,
            "action_card": {"state": state, "executable": False, "reason": "Mini command"}, "attempts": []}

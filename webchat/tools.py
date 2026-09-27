"""Web Bob's allowlisted tool layer.

This is the only way Web Bob can act on the mini instead of just talking about
it. Every call goes through `dispatch()`: name must be in `_HANDLERS` (nothing
else is reachable), the combined name+args text is scanned against the hard
blocks below, the handler runs, and the result is appended to
conductor/state/events.jsonl (`alignment_events`) so it shows up as a card with
a 30s undo window where an inverse action exists.

Hard-blocked, always, regardless of caller or phrasing: merge, undraft,
force-push, sending texts/emails/DMs/posts, spending past the metered cap,
deleting anything outside a worktree, and using Grok as a worker. None of the
handlers below implement any of those actions in the first place; the scanner
is defense in depth, not the only guard.

Lane requests with a durable queue id ask the scheduler to dispatch that job.
Only a worker receipt can report a started lane. Name-only requests remain events.
"""
from __future__ import annotations

import json
import fcntl
import re
import sys
import threading
import time
from pathlib import Path

from billing import MINIMAX_CAP_USD
from failover import atomic_text
from job_queue import council_job_description, queue_draft, queue_store
from actions import queue_once
from lane_dispatch import start_request
from providers import KEY, clean_env, run

_HERE = Path(__file__).resolve().parent
_IMPORT_ROOT = _HERE.parent.parent
_STATE_MODULE_DIR = _HERE.parent / "state"
if str(_STATE_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_STATE_MODULE_DIR))
from alignment_events import append_event, read_events  # noqa: E402

UNDO_WINDOW_SECONDS = 30


class ToolError(RuntimeError):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Hard blocks — scanned against every dispatch() call before a handler runs.
# ---------------------------------------------------------------------------

_MERGE_RE = re.compile(r"\bmerge(?:d|s|ing)?\b|\bgh\s+pr\s+merge\b", re.I)
_UNDRAFT_RE = re.compile(r"\bundraft(?:ed|ing)?\b|\bgh\s+pr\s+ready\b|--ready\b|\bmark\s+ready\s+for\s+review\b", re.I)
_FORCE_RE = re.compile(r"--force\b|force[- ]push|\+refs/", re.I)
_SEND_RE = re.compile(
    r"\bsend\s+(?:a\s+|an\s+)?(?:text|sms|email|dm|direct message|imessage)\b"
    r"|\bpost(?:ed|ing)?\s+(?:to|on)\s+(?:twitter|slack|discord|instagram)\b",
    re.I,
)
_GROK_RE = re.compile(r"\bgrok\b", re.I)
_SPEND_RE = re.compile(r"\b(?:buy|purchase|subscribe|upgrade\s+plan|change\s+(?:the\s+)?(?:login|password))\b", re.I)
_DELETE_RE = re.compile(r"\brm\s+-rf\b|\bgit\s+clean\s+-f|\breset\s+--hard\b", re.I)

_HARD_BLOCKS = (
    ("merge", _MERGE_RE, "This tool layer never merges."),
    ("undraft", _UNDRAFT_RE, "This tool layer never marks a PR ready or undrafts it."),
    ("force-push", _FORCE_RE, "This tool layer never force-pushes."),
    ("send-message", _SEND_RE, "This tool layer never sends texts, emails, DMs or posts."),
    ("grok-worker", _GROK_RE, "Grok is never used as a worker."),
    ("spend", _SPEND_RE, "This tool layer never purchases, upgrades plans, or changes logins."),
    ("destructive-delete", _DELETE_RE, "This tool layer never force-cleans or hard-resets."),
)


def _scan_hard_blocks(name: str, args: dict) -> None:
    haystack = name + " " + json.dumps(args, default=str, ensure_ascii=False)
    for code, pattern, message in _HARD_BLOCKS:
        if pattern.search(haystack):
            raise ToolError(code, message)


def _safe_args(args: dict) -> str:
    try:
        text = json.dumps(args, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(args)
    return KEY.sub("[secret removed]", text)[:2000]


# ---------------------------------------------------------------------------
# Path/branch guards
# ---------------------------------------------------------------------------

_SENSITIVE_PATH_RE = re.compile(
    r"(?:^|/)(?:keys\.env|\.password|\.env|cookies?|session|credentials?|\.git/config)(?:$|/)", re.I,
)


def _safe_repo_path(root: Path, relpath) -> Path:
    if not isinstance(relpath, str) or not relpath or relpath.startswith(("/", "~")) or ".." in Path(relpath).parts:
        raise ToolError("outside-worktree", "Path must be a relative path inside this worktree.")
    root_resolved = root.resolve()
    resolved = (root_resolved / relpath).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ToolError("outside-worktree", "Path escapes the current worktree.")
    if _SENSITIVE_PATH_RE.search(relpath.replace("\\", "/")):
        raise ToolError("blocked-secret", "Refusing to touch a credentials/session file.")
    return resolved


def _current_branch(root: Path, cancel: threading.Event) -> str:
    code, out, err = run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
                          cwd=root, env=clean_env(), cancel=cancel, timeout=10)
    if code != 0:
        raise ToolError("git", err.strip() or out.strip() or "Could not determine the current branch.")
    return out.strip()


def _current_head(root: Path, cancel: threading.Event) -> str:
    code, out, err = run(["git", "rev-parse", "HEAD"], cwd=root, env=clean_env(), cancel=cancel, timeout=10)
    if code != 0:
        raise ToolError("git", err.strip() or "git rev-parse failed.")
    return out.strip()


def _require_draft_branch(root: Path, cancel: threading.Event) -> str:
    branch = _current_branch(root, cancel)
    if not branch.startswith("draft/"):
        raise ToolError("not-draft-branch", f"Refusing: current branch `{branch}` is not a draft/ branch.")
    return branch


def _minimax_committed_usd(root: Path) -> float:
    path = root / "conductor/ledger/minimax.jsonl"
    if not path.exists():
        return 0.0
    total = 0.0
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            value = row.get("cost_usd")
            if value is None:
                value = row.get("reserved_usd", 0)
            total += float(value or 0)
    except OSError:
        return 0.0
    return total


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

def read_file(root: Path, path: str, *, cancel=None) -> dict:
    safe = _safe_repo_path(root, path)
    if not safe.is_file():
        raise ToolError("not-found", f"No such file: {path}")
    try:
        text = safe.read_text(errors="replace")
    except OSError as exc:
        raise ToolError("io-error", str(exc)) from None
    redacted = KEY.sub("[secret removed]", text)
    truncated = len(redacted) > 200_000
    return {
        "ok": True,
        "summary": f"Read `{path}` ({len(redacted)} chars{', truncated' if truncated else ''}).",
        "data": {"path": path, "text": redacted[:200_000], "truncated": truncated},
    }


# ---------------------------------------------------------------------------
# Queue tools (next-prompts/INDEX.md — the same file the scheduler reads)
# ---------------------------------------------------------------------------

_ROW_RE = re.compile(
    r"^\|\s*(?P<pri>\d+)\s*\|\s*`(?P<file>[^`]+)`\s*\|[^|]*\|[^|]*\|\s*(?P<status>[A-Za-z]+)\s*\|.*\|\s*$"
)
_VALID_STATUSES = {"READY", "CANCELLED", "PAUSED"}


def _index_path(root: Path) -> Path:
    return root / "next-prompts/INDEX.md"


def _rewrite_row(root: Path, filename: str, group: str, new_value) -> str:
    # Serialize edits with assignment as well as the producer journal writes.
    locks = root / "conductor/locks"
    locks.mkdir(parents=True, exist_ok=True)
    with (locks / "queue.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _rewrite_pending_row(root, filename, group, new_value)


def _rewrite_pending_row(root: Path, filename: str, group: str, new_value) -> str:
    path = _index_path(root)
    if not path.exists():
        raise ToolError("not-found", "Queue index does not exist yet.")
    lines = path.read_text().splitlines()
    old_value = None
    for index, line in enumerate(lines):
        match = _ROW_RE.match(line)
        if match and match.group("file") == filename:
            old_value = match.group(group)
            start, end = match.span(group)
            lines[index] = line[:start] + str(new_value) + line[end:]
            break
    if old_value is None:
        raise ToolError("not-found", f"No queue row for `{filename}`.")
    conductor = root / "conductor"
    identifier = "queue-" + Path(filename).stem
    if identifier in queue_store.snapshot(conductor=conductor):
        fields = {"priority": int(new_value)} if group == "pri" else {
            "status": {"READY": "queued", "PAUSED": "blocked", "CANCELLED": "cancelled"}[new_value]}
        try:
            queue_store.edit_pending(identifier, conductor=conductor, **fields)
        except ValueError as exc:
            raise ToolError("already-assigned", str(exc)) from exc
    atomic_text(path, "\n".join(lines) + "\n")
    return old_value.strip()


def queue_add(root: Path, description: str, *, action_id=None, cancel=None) -> dict:
    if not isinstance(description, str) or not description.strip():
        raise ToolError("invalid-args", "Job description is required.")
    result = queue_once(root, action_id, description.strip()) if action_id else queue_draft(root, description.strip())
    if not result.get("ok"):
        raise ToolError("blocked", result.get("error", "Could not queue job."))
    return {
        "ok": True,
        "summary": f"Queued draft job `{result['file']}`.",
        "data": result,
        "undo": {"tool": "queue_set_status", "args": {"filename": result["file"], "status": "CANCELLED"}},
    }


def queue_split(root: Path, description: str, parts: list, *, cancel=None) -> dict:
    if not isinstance(description, str) or not description.strip():
        raise ToolError("invalid-args", "Job description is required.")
    if not isinstance(parts, list) or not (2 <= len(parts) <= 10):
        raise ToolError("invalid-args", "Provide 2-10 parts to split into.")
    created = []
    for index, part in enumerate(parts, start=1):
        if not isinstance(part, str) or not part.strip():
            raise ToolError("invalid-args", f"Part {index} is empty.")
        sub = f"{description.strip()} — part {index}/{len(parts)}: {part.strip()}"
        result = queue_draft(root, sub)
        if not result.get("ok"):
            raise ToolError("blocked", result.get("error", "Could not queue part."))
        created.append(result["file"])
    return {
        "ok": True,
        "summary": f"Queued {len(created)} split jobs.",
        "data": {"files": created},
        "undo": {"tool": "queue_cancel_many", "args": {"filenames": created}},
    }


def queue_prioritize(root: Path, filename: str, priority: int, *, cancel=None) -> dict:
    if isinstance(priority, bool) or not isinstance(priority, int) or not (1 <= priority <= 99):
        raise ToolError("invalid-args", "Priority must be an integer 1-99.")
    old_value = _rewrite_row(root, filename, "pri", priority)
    return {
        "ok": True,
        "summary": f"Reprioritized `{filename}` from {old_value} to {priority}.",
        "undo": {"tool": "queue_prioritize", "args": {"filename": filename, "priority": int(old_value)}},
    }


def queue_set_status(root: Path, filename: str, status: str, *, cancel=None) -> dict:
    if status not in _VALID_STATUSES:
        raise ToolError("invalid-args", f"Status must be one of {sorted(_VALID_STATUSES)}.")
    old_value = _rewrite_row(root, filename, "status", status)
    return {
        "ok": True,
        "summary": f"Set `{filename}` status to {status} (was {old_value}).",
        "undo": {"tool": "queue_set_status", "args": {"filename": filename, "status": old_value}},
    }


def queue_cancel(root: Path, filename: str, *, cancel=None) -> dict:
    result = queue_set_status(root, filename, "CANCELLED")
    result["summary"] = f"Cancelled queue row `{filename}` (was {result['undo']['args']['status']})."
    return result


def queue_cancel_many(root: Path, filenames: list, *, cancel=None) -> dict:
    if not isinstance(filenames, list) or not filenames:
        raise ToolError("invalid-args", "filenames must be a non-empty list.")
    for filename in filenames:
        queue_set_status(root, filename, "CANCELLED")
    return {"ok": True, "summary": f"Cancelled {len(filenames)} queue rows.", "data": {"files": filenames}}


# ---------------------------------------------------------------------------
# Lane control — a REQUEST for the scheduler; never touches services/job-runner
# ---------------------------------------------------------------------------

_LANE_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$", re.I)


def _request_lane(root: Path, lane: str, reason: str, action: str) -> dict:
    if not isinstance(lane, str) or not _LANE_NAME_RE.match(lane):
        raise ToolError("invalid-args", "Lane name must be alphanumeric/dash, max 40 chars.")
    reason = (reason or "")[:300]
    opposite = "stop" if action == "start" else "start"
    return {
        "ok": True,
        "kind": f"lane_{action}_request",
        "summary": (
            f"Filed a {action} request for lane `{lane}`"
            + (f": {reason}" if reason else "")
            + ". The scheduler decides whether to act — this does not spawn or kill anything directly."
        ),
        "data": {"lane": lane, "reason": reason},
        "undo": {"tool": f"request_lane_{opposite}", "args": {"lane": lane, "reason": "undo of prior request"}},
    }


def request_lane_start(root: Path, lane: str, reason: str = "", *, request_id=None, cancel=None) -> dict:
    if request_id is not None:
        if lane != "auto":
            raise ToolError("invalid-args", "Use lane=auto for a queue request; the scheduler selects an eligible lane.")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", request_id):
            raise ToolError("invalid-args", "A valid durable queue id is required.")
        result = start_request(root, request_id, cancel=cancel)
        summary = (f"Started lane `{result['lane']}` for `{request_id}` (worker `{result['execution_id']}`)."
                   if result.get("started") else result.get("reason") or "Waiting for an eligible lane.")
        return {"ok": True, "kind": "lane_started" if result.get("started") else "lane_start_pending",
                "summary": summary, "data": result}
    return _request_lane(root, lane, reason, "start")


def request_lane_stop(root: Path, lane: str, reason: str = "", *, cancel=None) -> dict:
    return _request_lane(root, lane, reason, "stop")


# ---------------------------------------------------------------------------
# Council
# ---------------------------------------------------------------------------

def run_council(root: Path, question: str, *, cancel=None) -> dict:
    if not isinstance(question, str) or not question.strip():
        raise ToolError("invalid-args", "A council question is required.")
    committed = _minimax_committed_usd(root)
    if committed >= MINIMAX_CAP_USD:
        raise ToolError(
            "blocked-cap",
            f"MiniMax spend (${committed:.2f}) is at or over the ${MINIMAX_CAP_USD:.0f} cap; council was not queued.",
        )
    description = council_job_description(question)
    result = queue_draft(root, description)
    if not result.get("ok"):
        raise ToolError("blocked", result.get("error", "Could not queue council."))
    return {
        "ok": True,
        "summary": f"Queued draft council run `{result['file']}` (Gemini + MiniMax + Claude; no Grok).",
        "data": result,
        "undo": {"tool": "queue_set_status", "args": {"filename": result["file"], "status": "CANCELLED"}},
    }


# ---------------------------------------------------------------------------
# Tests / drills (isolated: only these named, known-offline entrypoints)
# ---------------------------------------------------------------------------

_TEST_TARGETS = {
    "webchat": Path("webchat/test_webchat.py"),
    "failover": Path("webchat/test_failover.py"),
    "services": Path("services/test_services.py"),
    "council": Path("services/test_council.py"),
}
_DRILL_TARGETS = {
    "ready": Path("webchat/live_ready_drill.py"),
    "handback": Path("webchat/live_handback_drill.py"),
}


def run_tests(root: Path, target: str, *, cancel=None) -> dict:
    cancel = cancel or threading.Event()
    if target not in _TEST_TARGETS:
        raise ToolError("invalid-args", f"target must be one of {sorted(_TEST_TARGETS)}.")
    path = root / _TEST_TARGETS[target]
    if not path.is_file():
        raise ToolError("not-found", f"{path} not found.")
    code, out, err = run([sys.executable, str(path)], cwd=path.parent, env=clean_env(), cancel=cancel, timeout=180)
    ok = code == 0
    return {
        "ok": ok,
        "summary": f"`{target}` tests {'passed' if ok else 'FAILED'} (exit {code}).",
        "data": {"output_tail": (out + err)[-4000:]},
    }


def run_drill(root: Path, name: str, *, cancel=None) -> dict:
    cancel = cancel or threading.Event()
    if name not in _DRILL_TARGETS:
        raise ToolError("invalid-args", f"name must be one of {sorted(_DRILL_TARGETS)}.")
    path = root / _DRILL_TARGETS[name]
    if not path.is_file():
        raise ToolError("not-found", f"{path} not found.")
    code, out, err = run([sys.executable, str(path)], cwd=path.parent, env=clean_env(), cancel=cancel, timeout=120)
    ok = code == 0
    return {
        "ok": ok,
        "summary": f"`{name}` drill {'passed' if ok else 'FAILED'} (exit {code}).",
        "data": {"output_tail": (out + err)[-4000:]},
    }


# ---------------------------------------------------------------------------
# Git / gh — draft/ branches only for anything that mutates or publishes
# ---------------------------------------------------------------------------

def git_status(root: Path, *, cancel=None) -> dict:
    cancel = cancel or threading.Event()
    code, out, err = run(["git", "status", "--porcelain=v1", "--branch"],
                          cwd=root, env=clean_env(), cancel=cancel, timeout=15)
    if code != 0:
        raise ToolError("git", err.strip() or "git status failed.")
    return {"ok": True, "summary": "git status read.", "data": {"status": out}}


def git_diff(root: Path, path: str | None = None, *, cancel=None) -> dict:
    cancel = cancel or threading.Event()
    argv = ["git", "diff"]
    if path is not None:
        safe = _safe_repo_path(root, path)
        argv += ["--", str(safe.relative_to(root.resolve()))]
    code, out, err = run(argv, cwd=root, env=clean_env(), cancel=cancel, timeout=20)
    if code != 0:
        raise ToolError("git", err.strip() or "git diff failed.")
    return {"ok": True, "summary": f"git diff read ({len(out)} chars).", "data": {"diff": out[:200_000]}}


def git_branch(root: Path, *, cancel=None) -> dict:
    cancel = cancel or threading.Event()
    branch = _current_branch(root, cancel)
    return {"ok": True, "summary": f"On branch `{branch}`.", "data": {"branch": branch}}


def git_commit(root: Path, message: str, paths: list | None = None, *, cancel=None) -> dict:
    cancel = cancel or threading.Event()
    if not isinstance(message, str) or not message.strip() or len(message) > 500:
        raise ToolError("invalid-args", "Commit message must be 1-500 characters.")
    branch = _require_draft_branch(root, cancel)
    if paths:
        safe_paths = [str(_safe_repo_path(root, p).relative_to(root.resolve())) for p in paths]
        code, out, err = run(["git", "add", "--", *safe_paths], cwd=root, env=clean_env(), cancel=cancel, timeout=15)
        if code != 0:
            raise ToolError("git", err.strip() or "git add failed.")
        commit_argv = ["git", "commit", "-m", message]
    else:
        commit_argv = ["git", "commit", "-a", "-m", message]
    code, out, err = run(commit_argv, cwd=root, env=clean_env(), cancel=cancel, timeout=20)
    if code != 0:
        raise ToolError("git", err.strip() or out.strip() or "git commit failed (nothing to commit?).")
    sha = _current_head(root, cancel)
    return {"ok": True, "summary": f"Committed on `{branch}` ({sha[:12]}).", "data": {"branch": branch, "sha": sha}}


def git_push(root: Path, *, cancel=None) -> dict:
    cancel = cancel or threading.Event()
    branch = _require_draft_branch(root, cancel)
    code, out, err = run(["git", "push", "-u", "origin", branch], cwd=root, env=clean_env(), cancel=cancel, timeout=60)
    if code != 0:
        raise ToolError("git", err.strip() or "git push failed.")
    return {"ok": True, "summary": f"Pushed `{branch}` to origin.", "data": {"branch": branch}}


def open_draft_pr(root: Path, title: str, body: str = "", *, cancel=None) -> dict:
    cancel = cancel or threading.Event()
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ToolError("invalid-args", "PR title must be 1-200 characters.")
    if not isinstance(body, str) or len(body) > 4000:
        raise ToolError("invalid-args", "PR body is too long.")
    branch = _require_draft_branch(root, cancel)
    argv = ["gh", "pr", "create", "--draft", "--title", title, "--body", body, "--head", branch]
    code, out, err = run(argv, cwd=root, env=clean_env(), cancel=cancel, timeout=30)
    if code != 0:
        raise ToolError("gh", err.strip() or out.strip() or "gh pr create failed.")
    return {"ok": True, "summary": f"Opened draft PR for `{branch}`.", "data": {"url": out.strip()}}


def read_ci(root: Path, *, cancel=None) -> dict:
    cancel = cancel or threading.Event()
    code, out, err = run(["gh", "pr", "checks"], cwd=root, env=clean_env(), cancel=cancel, timeout=30)
    if code not in (0, 1):
        raise ToolError("gh", err.strip() or "gh pr checks failed.")
    return {"ok": True, "summary": "CI status read.", "data": {"checks": out}}


# ---------------------------------------------------------------------------
# Registry + dispatch
# ---------------------------------------------------------------------------

_HANDLERS = {
    "read_file": read_file,
    "queue_add": queue_add,
    "queue_split": queue_split,
    "queue_prioritize": queue_prioritize,
    "queue_set_status": queue_set_status,
    "queue_cancel": queue_cancel,
    "queue_cancel_many": queue_cancel_many,
    "request_lane_start": request_lane_start,
    "request_lane_stop": request_lane_stop,
    "run_council": run_council,
    "run_tests": run_tests,
    "run_drill": run_drill,
    "git_status": git_status,
    "git_diff": git_diff,
    "git_branch": git_branch,
    "git_commit": git_commit,
    "git_push": git_push,
    "open_draft_pr": open_draft_pr,
    "read_ci": read_ci,
}

TOOL_SPECS = [
    {"name": "read_file", "description": "Read a repo-relative text file (never credentials/session files).",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "queue_add", "description": "Queue a new draft job for the scheduler.",
     "input_schema": {"type": "object", "properties": {"description": {"type": "string"},
         "action_id": {"type": "string"}}, "required": ["description"]}},
    {"name": "queue_split", "description": "Queue a job split into 2-10 parts.",
     "input_schema": {"type": "object", "properties": {
         "description": {"type": "string"}, "parts": {"type": "array", "items": {"type": "string"}}},
         "required": ["description", "parts"]}},
    {"name": "queue_prioritize", "description": "Change the priority (1-99) of a queued job.",
     "input_schema": {"type": "object", "properties": {
         "filename": {"type": "string"}, "priority": {"type": "integer"}}, "required": ["filename", "priority"]}},
    {"name": "queue_set_status", "description": "Set a queued job's status to READY, PAUSED or CANCELLED.",
     "input_schema": {"type": "object", "properties": {
         "filename": {"type": "string"}, "status": {"type": "string"}}, "required": ["filename", "status"]}},
    {"name": "queue_cancel", "description": "Cancel a queued job (marks CANCELLED; never deletes the row).",
     "input_schema": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}},
    {"name": "queue_cancel_many", "description": "Cancel several queued jobs at once.",
     "input_schema": {"type": "object", "properties": {
         "filenames": {"type": "array", "items": {"type": "string"}}}, "required": ["filenames"]}},
    {"name": "request_lane_start", "description": "With request_id and lane=auto, dispatch one durable job and return observed worker evidence; otherwise file a lane request.",
     "input_schema": {"type": "object", "properties": {
         "lane": {"type": "string"}, "reason": {"type": "string"},
         "request_id": {"type": "string"}}, "required": ["lane"]}},
    {"name": "request_lane_stop", "description": "File a request for the scheduler to stop a lane. Never kills anything itself.",
     "input_schema": {"type": "object", "properties": {
         "lane": {"type": "string"}, "reason": {"type": "string"}}, "required": ["lane"]}},
    {"name": "run_council", "description": "Queue a draft council run (Gemini + MiniMax + Claude; never Grok).",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    {"name": "run_tests", "description": "Run one allowlisted offline test suite.",
     "input_schema": {"type": "object", "properties": {
         "target": {"type": "string", "enum": sorted(_TEST_TARGETS)}}, "required": ["target"]}},
    {"name": "run_drill", "description": "Run one allowlisted isolated drill.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string", "enum": sorted(_DRILL_TARGETS)}}, "required": ["name"]}},
    {"name": "git_status", "description": "Read `git status --porcelain --branch`.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "git_diff", "description": "Read `git diff`, optionally scoped to one path.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "git_branch", "description": "Read the current branch name.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "git_commit", "description": "Commit tracked changes. draft/ branches only.",
     "input_schema": {"type": "object", "properties": {
         "message": {"type": "string"}, "paths": {"type": "array", "items": {"type": "string"}}},
         "required": ["message"]}},
    {"name": "git_push", "description": "Push the current branch to origin. draft/ branches only; never force.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "open_draft_pr", "description": "Open a DRAFT pull request via gh for the current draft/ branch.",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"}, "body": {"type": "string"}}, "required": ["title"]}},
    {"name": "read_ci", "description": "Read CI check status for the current branch's PR via `gh pr checks`.",
     "input_schema": {"type": "object", "properties": {}}},
]


def list_tools() -> list:
    return [dict(spec) for spec in TOOL_SPECS]


def dispatch(name: str, args: dict | None = None, *, root: Path, actor: str = "web-bob", cancel=None) -> dict:
    args = dict(args or {})
    if name not in _HANDLERS:
        raise ToolError("unknown-tool", f"`{name}` is not an allowlisted tool.")
    _scan_hard_blocks(name, args)
    cancel = cancel or threading.Event()
    try:
        result = _HANDLERS[name](root, cancel=cancel, **args)
    except TypeError as exc:
        raise ToolError("invalid-args", str(exc)) from exc
    result.setdefault("ok", True)
    kind = result.pop("kind", "tool:" + name)
    undo_payload = result.get("undo")
    expires_at = time.time() + UNDO_WINDOW_SECONDS if undo_payload else None
    seq = append_event(
        root, actor=actor, kind=kind,
        summary=result.get("summary", name)[:500],
        tool=name, args=_safe_args(args), ok=bool(result.get("ok")),
        undo=undo_payload, undo_expires_at=expires_at,
    )
    return {**result, "event_seq": seq, "undo_expires_at": expires_at}


def undo(event_seq: int, *, root: Path, actor: str = "web-bob") -> dict:
    events = read_events(root, since_seq=max(0, event_seq - 1))
    row = next((event for event in events if event.get("seq") == event_seq), None)
    if row is None:
        raise ToolError("not-found", f"No event #{event_seq}.")
    payload = row.get("undo")
    if not payload:
        raise ToolError("no-undo", f"Event #{event_seq} has no undo action.")
    expires_at = row.get("undo_expires_at")
    if expires_at is not None and time.time() > expires_at:
        raise ToolError("undo-expired", f"The {UNDO_WINDOW_SECONDS}s undo window for event #{event_seq} has passed.")
    result = dispatch(payload["tool"], payload.get("args", {}), root=root, actor=actor + ":undo")
    result["summary"] = f"Undid event #{event_seq}: {result['summary']}"
    return result


# ---------------------------------------------------------------------------
# Chat-facing: recognize Jeff's "you're too limited" frustration and answer
# with the real, concrete command list instead of a read-only refusal.
# ---------------------------------------------------------------------------

_CAPABILITY_ASK_RE = re.compile(
    r"\bi need you to do more\b|\bdo more than (?:that|this)\b|\bstop being read-?only\b"
    r"|\byou'?re too limited\b|\bwhy can'?t you (?:just )?do it\b|\bdo it yourself\b"
    r"|\bstop telling me to (?:ask|do it)\b|\bjust do it\b",
    re.I,
)


def try_capability_reply(text: str) -> str | None:
    if not _CAPABILITY_ASK_RE.search(text or ""):
        return None
    names = ", ".join(f"`{spec['name']}`" for spec in TOOL_SPECS)
    return (
        "Fair — I'm not read-only. I have a real allowlisted tool layer and can act directly: "
        + names + ". Tell me which one and the details "
        "(for example \"prioritize webchat-20260927-ab12.md to 5\" or \"open a draft PR titled ...\") "
        "and it runs for real, logged to events.jsonl with a 30s undo where one applies. "
        "I still never merge, undraft, force-push, spend past the MiniMax cap, delete outside a worktree, "
        "or use Grok as a worker — and I won't claim something ran unless the exact command already did."
    )

"""Durable Web Bob tasks. Reads observe; locked writers repair and commit."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import time
import uuid
from pathlib import Path
from api_tasks import REPORT_KINDS, normalize_kind

MODEL_WORKERS = ("codex", "claude", "cursor", "gemini", "minimax")
API_WORKERS = ("gemini", "minimax")
WORKERS = (*MODEL_WORKERS, "mini")
CONCURRENCY = {"gemini": 3, "minimax": 3}
ACTIVE = ("claimed", "running")
TERMINAL = ("succeeded", "failed")
LEASE_SECONDS = 90
MAX_ATTEMPTS = 3


class AdmissionPaused(ValueError):
    pass


def file_request(prompt):
    """A small explicit temporary-file task may use any tool-capable CLI."""
    match = re.fullmatch(r"(?:please\s+)?write\s+([^\n]{1,1000}?)\s+to\s+(/tmp/[A-Za-z0-9_-]+\.(?:txt|md|json))\s*", prompt, re.I)
    return (match[1].strip("\"'"), match[2]) if match else None


def file_task_kind(prompt):
    """Recognize requested local file access, not file names in supplied code.

    Max-mode packages carry the overall goal before their own assignment. Only
    the assignment determines whether that particular worker needs tools.
    Ambiguous requests still have to pass task-aware result acceptance.
    """
    task = prompt.rsplit("Your independent subtask:", 1)[-1]
    task = re.sub(r"```.*?```", "", task, flags=re.S)
    task = re.split(r"\n\s*(?:SUPPLIED EVIDENCE|EVIDENCE|SOURCE|CODE)\s*:", task, maxsplit=1, flags=re.I)[0]
    read = r"(?:read|open|inspect|review|audit|summari[sz]e|analy[sz]e|check|list|search)"
    write = r"(?:write|save|create|make|build|prepare|produce|put together|edit|modify|update|delete|remove|append)"
    # A path is an instruction target only after a task verb. 'Explain how to
    # read a file' and pasted source mentioning paths remain answer-only work.
    start = r"(?:^|[\n.;]\s*|\band\s+|\bthen\s+)\s*(?:please\s+)?"
    qualifiers = r"(?:(?:the|this|that|local|actual|current|our|my|all|contents of|files in|source in|read-only)\s+){0,5}"
    # Slash-separated concepts such as input/output are not local paths.
    target = (r"[`\"']?(?:(?:/|\./|\.\./|~/)[\w./-]+|(?:[\w.-]+/)+[\w.-]+\.[\w]+\b|"
              r"(?:services|webchat|conductor|state|src|lib|tests|docs|config|reviews)/[\w./-]*|"
              r"[\w-]+\.(?:py|md|txt|json|js|ts|tsx|jsx|sh|yaml|yml|toml|csv|log)\b|"
              r"(?:git\s+)?(?:worktree|checkout|repository|repo|directory|folder|files?)\b)")
    # Quoted commands are examples, not action clauses. Preserve literal path
    # arguments, including backticked filenames, without adopting other text.
    task = re.sub(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`|(?<!\w)\x27[^\x27\n]*\x27(?!\w)',
                  lambda m: m[0][1:-1] if re.fullmatch(target, m[0][1:-1], re.I) else '', task)
    if (re.search(start + write + r"\s+" + qualifiers + target, task, re.I) or
            re.search(start + write + r"\b[^\n]{0,120}\b(?:to|in|under|at)\s+" +
                      qualifiers + target, task, re.I)):
        return "coding"
    if re.search(start + read + r"\s+" + qualifiers + target, task, re.I):
        return "inspection"
    return None


def needs_files(prompt):
    return file_task_kind(prompt) is not None


def task_kind(kind, prompt):
    if kind == "analysis":
        return file_task_kind(prompt) or kind
    return kind


def validate_worker(worker, kind):
    if worker != "auto" and worker not in worker_order(kind):
        if worker == "minimax" and kind == "research":
            raise ValueError("Research with google_search requires Gemini. MiniMax can review evidence, draft tests and grade evals.")
        if worker in API_WORKERS:
            raise ValueError(worker + " is API-only: it can audit, plan, research, review, draft tests or grade evals "
                             "into reviews/. It cannot edit project files, deploy, resolve conflicts or run commands. "
                             "Choose codex or cursor-agent for that work.")
        raise ValueError("This task needs a compatible tool worker: " + ", ".join(worker_order(kind)) + ".")


def worker_name(value):
    value = {"cursor-agent": "cursor", "mini CPU": "mini"}.get(value, value)
    if value not in (*WORKERS, "auto"):
        raise ValueError("Choose codex, claude, cursor-agent, gemini, minimax, or mini; never Grok.")
    return value


@contextlib.contextmanager
def locked(root, *, read_only=False):
    folder = Path(root) / "conductor/state"
    if read_only:
        try:
            handle = (folder / ".queue.lock").open("rb")
        except FileNotFoundError:
            # An empty or imported journal need not have a writer lock yet.
            # Observe its bytes without creating state. A concurrent first
            # append can at most expose an incomplete final record to _read.
            yield folder / "queue.jsonl"
            return
        with handle:
            fcntl.flock(handle, fcntl.LOCK_SH)
            yield folder / "queue.jsonl"
        return
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".queue.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield folder / "queue.jsonl"


def _read(path, *, repair=True):
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return {}
    rows, offset = {}, 0
    for line in data.splitlines(keepends=True):
        try:
            row = json.loads(line)
            rows[row["id"]] = row
        except (ValueError, KeyError, TypeError):
            if offset + len(line) != len(data) or line.endswith(b"\n"):
                raise ValueError("Task queue corruption; refusing to discard committed records") from None
            # Readers return the intact prefix. Only a locked writer may
            # discard a torn append before committing its next transition.
            if repair:
                with path.open("r+b") as handle:
                    handle.truncate(offset)
                    handle.flush()
                    os.fsync(handle.fileno())
            break
        offset += len(line)
    if repair and data and not data.endswith(b"\n") and offset == len(data):
        with path.open("ab") as handle:
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    return rows


def _append(path, row, event, now=None):
    row = dict(row, event=event, updated_at=time.time() if now is None else now)
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return row


def tasks(root):
    """Observe queue state without creating files or repairing journal bytes."""
    with locked(root, read_only=True) as path:
        return _read(path, repair=False)


def worker_order(kind):
    if kind in REPORT_KINDS:
        return ("gemini",) if kind == "research" else (("gemini", "minimax") if kind in ("audit", "planning") else ("minimax", "gemini"))
    return {"coding": ("codex", "cursor"), "artifact": ("codex", "cursor", "claude"), "local": ("mini",),
            "inspection": ("codex", "cursor"),
            "analysis": ("claude", "gemini", "minimax", "codex", "cursor")}[kind]


def capacity(worker):
    return CONCURRENCY.get(worker, 1)


def group_complete(members):
    if not members:
        return False
    first = members[0]
    size = first.get("group_size")
    return (type(size) is int and 2 <= size <= 24 and len(members) == size
            and {r.get("group_index") for r in members} == set(range(size))
            and all((r.get("group_size"), r.get("conversation_id"), r.get("group_goal")) ==
                    (size, first.get("conversation_id"), first.get("group_goal")) for r in members))


def enqueue(root, conversation_id, request_id, prompt, *, worker="auto", kind="analysis", source_file=None,
            group_id=None, group_size=None, group_index=None, group_goal=None, title=None, local_suite=None,
            publish_project=None, draft_pr=False, source_job_id=None, permission_file=None, project_scopes=None,
            expected_code_identity=None):
    worker = worker_name(worker)
    if worker == "mini":
        kind = "local"
    kind = normalize_kind(worker, task_kind(kind, prompt), prompt)
    if kind not in ("analysis", "inspection", "coding", "artifact", "local", *REPORT_KINDS) or not prompt.strip():
        raise ValueError("Task needs a description and a supported kind")
    if kind == "artifact" and not file_request(prompt):
        raise ValueError("Small file tasks require an explicit text and /tmp file destination")
    validate_worker(worker, kind)
    if publish_project is not None and (kind != "coding" or publish_project not in ("WebJam", "AdoptIQ", "StoryBoard", "Fantasy Football", "Shelf", "Web Bob")):
        raise ValueError("Draft publication requires an explicit coding project")
    if draft_pr and not publish_project:
        raise ValueError("Draft PR requires a project publication")
    if group_id and (type(group_size) is not int or not 2 <= group_size <= 24 or
                     type(group_index) is not int or not 0 <= group_index < group_size):
        raise ValueError("A task group requires a valid size and unique subtask index")
    key = "webbob:" + str(conversation_id) + ":" + str(request_id)
    identifier = "webchat-" + uuid.uuid5(uuid.NAMESPACE_URL, key).hex
    with locked(root) as path:
        rows = _read(path)
        if identifier in rows:
            row = rows[identifier]
            if (row["prompt"], row["requested_worker"], row["kind"], row.get("group_id"), row.get("group_size"),
                row.get("group_index"), row.get("group_goal"), row.get("title"), row.get("local_suite"), row.get("publish_project"), row.get("draft_pr", False), row.get("source_job_id")) != (
                    prompt, worker, kind, group_id, group_size, group_index, group_goal, title, local_suite, publish_project, draft_pr, source_job_id):
                raise ValueError("This request ID already belongs to a different task")
            if row.get('expected_code_identity') != expected_code_identity:
                raise ValueError('This request ID belongs to a different source revision')
            if permission_file:
                if row.get('permission_file') and (row['permission_file'] != str(permission_file)
                        or row.get('project_scopes', []) != list(project_scopes or [])):
                    raise ValueError('This request ID already has different permission scope')
                if not row.get('permission_file'):
                    row.update(permission_file=str(permission_file), project_scopes=list(project_scopes or []))
                    _append(path, row, 'permission_bound')
            return row
        if permission_file and (Path(root) / 'conductor/locks/webbob-activation.json').exists():
            raise AdmissionPaused('Release verification is in progress; no worker job was queued.')
        for member in (r for r in rows.values() if group_id and r.get("group_id") == group_id):
            if (member.get("group_index") == group_index or
                (member.get("group_size"), member.get("conversation_id"), member.get("group_goal")) !=
                    (group_size, conversation_id, group_goal)):
                raise ValueError("Conflicting task group membership")
        return _append(path, dict(id=identifier, conversation_id=conversation_id, request_id=request_id,
                                 prompt=prompt, requested_worker=worker, kind=kind, source_file=source_file,
                                 status="queued", attempts=0, created_at=time.time(), delivered_at=None,
                                 group_id=group_id, group_size=group_size, group_index=group_index,
                                 group_goal=group_goal, title=title, local_suite=local_suite, publish_project=publish_project, draft_pr=draft_pr,
                                 source_job_id=source_job_id,
                                 permission_file=str(permission_file) if permission_file else None,
                                 project_scopes=list(project_scopes or []),
                                 expected_code_identity=expected_code_identity,
                                 tried_workers=[], max_attempts=max(MAX_ATTEMPTS, len(worker_order(kind))),
                                 worker=None, claim_token=None, lease_until=0, retry_at=0), "enqueued")


def permission_block(root, row):
    """Observe saved user holds, never model prose. Caller owns the queue lock.

    Legacy chat jobs are checked when their canonical conversation still exists.
    Standalone scheduler jobs without a chat do not inherit another chat's holds.
    New chat jobs bind their permission file and fail closed if it disappears.
    """
    explicit = row.get('permission_file')
    path = Path(explicit) if explicit else Path(root) / 'conductor/webchat/sessions' / (str(row.get('conversation_id')) + '.json')
    if not explicit and not path.exists():
        return None
    try:
        with path.open('rb') as handle:
            data = handle.read(10_000_001)
        if len(data) > 10_000_000:
            return 'Saved conversation permissions exceed the read limit'
        conversation = json.loads(data)
        if conversation.get('id') != row.get('conversation_id'):
            return 'Saved conversation identity mismatch'
        goal = conversation.get('improvement_goal') or {}
        if (goal.get('verification_request_id') == row.get('request_id')
                and goal.get('execution_restriction')):
            return 'The owner limited this improvement goal to inspection; execution is not authorized'
        holds = conversation['intent_state']['holds']
        scopes = row.get('project_scopes') or []
        if 'project_scopes' not in row:
            # Legacy rows predate explicit scope binding. Recognize only their
            # canonical project names; do not inherit every scoped hold.
            scopes = [name for name in ('Web Bob', 'WebJam', 'AdoptIQ', 'StoryBoard', 'Fantasy Football', 'Shelf')
                      if re.search(r'\b' + r'\s*'.join(map(re.escape, name.split())) + r'\b',
                                   row.get('prompt', ''), re.I)]
        for scope, hold in holds.items():
            if scope == 'all':
                if not scopes or any(name not in hold.get('released_projects', []) for name in scopes):
                    return 'New work is on hold'
            elif not scopes or scope in scopes:
                return scope + ' is on hold'
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return 'Saved conversation permissions are unavailable'
    return None


def claim(root, worker, now=None, *, identifier=None, allow_fallback=False, limit=None):
    worker = worker_name(worker)
    if worker == "auto":
        raise ValueError("Claims require an actual worker")
    now = time.time() if now is None else now
    with locked(root) as path:
        rows = _read(path)
        ceiling = capacity(worker) if limit is None else max(0, min(capacity(worker), int(limit)))
        if sum(r["status"] in ACTIVE and r["worker"] == worker for r in rows.values()) >= ceiling:
            return None
        for row in sorted(rows.values(), key=lambda r: r["created_at"]):
            if identifier and row["id"] != identifier:
                continue
            if row["status"] != "queued" or row.get("retry_at", 0) > now:
                continue
            if permission_block(root, row):
                continue
            if row["requested_worker"] not in ("auto", worker) and not allow_fallback:
                continue
            if worker not in worker_order(row["kind"]):
                continue
            if row.get("group_id") and not group_complete([r for r in rows.values() if r.get("group_id") == row["group_id"]]):
                continue  # Saved intent repairs an interrupted multi-row append before dispatch.
            row.update(status="claimed", worker=worker, claim_token=uuid.uuid4().hex,
                       claimed_at=now, lease_until=now + LEASE_SECONDS, attempts=row["attempts"] + 1,
                       pid=None, started_at=None, execution_started_at=None, error=None)
            return _append(path, row, "claimed", now)
    return None


def transition(root, identifier, token, event, *, now=None, **fields):
    now = time.time() if now is None else now
    with locked(root) as path:
        row = _read(path).get(identifier)
        if not row or row["status"] not in ACTIVE or row["claim_token"] != token or row["lease_until"] <= now:
            return None
        if event in ('running', 'executing'):
            blocked = permission_block(root, row)
            if blocked:
                row.update(status='queued', claim_token=None, lease_until=0, retry_at=0,
                           attempts=max(0, row['attempts'] - 1), error=blocked)
                _append(path, row, 'held_before_execution', now)
                return None
        if event == "running":
            row.update(status="running", started_at=now, pid=os.getpid())
        elif event == "executing":
            row.update(execution_started_at=now)
        elif event == "heartbeat":
            pass
        elif event == "succeeded":
            if not fields.get("result", "").strip():
                raise ValueError("An empty result cannot finish a task")
            row.update(status="succeeded", finished_at=now)
        elif event == "rejected":
            # An unusable answer is terminal, not a provider outage to retry
            # across every lane. Keep the rejection in the durable outbox.
            row.update(status="failed", finished_at=now, claim_token=None)
        elif event in ("retry", "busy"):
            if event == "busy":
                row["attempts"] -= 1  # A lane race is not a failed execution.
            if event == "retry":
                row["tried_workers"] = list(dict.fromkeys([*row.get("tried_workers", []), row["worker"]]))
            row.update(status="failed" if row["attempts"] >= row.get("max_attempts", MAX_ATTEMPTS) else "queued",
                       retry_at=now + (5 if event == "busy" else min(60, 5 * 2 ** row["attempts"])),
                       claim_token=None)
            if row["status"] == "failed":
                row["finished_at"] = now
        else:
            raise ValueError("Unknown task transition")
        row.update(fields, heartbeat_at=now, lease_until=now + LEASE_SECONDS if row["status"] in ACTIVE else 0)
        return _append(path, row, event, now)


def recover(root, worker_alive, now=None):
    """Requeue lost claims; a live expired execution must exit before replacement."""
    now = time.time() if now is None else now
    changed = []
    with locked(root) as path:
        for row in _read(path).values():
            if row["status"] not in ACTIVE:
                continue
            alive = worker_alive(row)
            # A freshly launched worker has time to acquire its execution lock.
            if alive or (row["status"] == "claimed" and row["lease_until"] > now):
                continue
            row["tried_workers"] = list(dict.fromkeys([*row.get("tried_workers", []), row["worker"]]))
            row.update(status="failed" if row["attempts"] >= row.get("max_attempts", MAX_ATTEMPTS) else "queued",
                       claim_token=None, lease_until=0, retry_at=now,
                       error="Worker exited before returning a result; claim recovered")
            if row["status"] == "failed":
                row["finished_at"] = now
            changed.append(_append(path, row, "recovered", now))
    return changed


def delivered(root, identifier, message_id):
    with locked(root) as path:
        row = _read(path)[identifier]
        if row["status"] not in TERMINAL:
            raise ValueError("Cannot acknowledge an unfinished result")
        if not row.get("delivered_at"):
            row.update(delivered_at=time.time(), result_message_id=message_id)
            return _append(path, row, "delivered")
        return row


def cancel_replay(root, conversation_ids, reason):
    """Fence only this release's replay jobs before restoring older workers.

    Keep receipts, drafts and completed results. Existing workers observe the
    revoked claim on their next heartbeat and cannot publish after rollback.
    """
    cancelled = []
    with locked(root) as path:
        for row in _read(path).values():
            if row.get("conversation_id") not in conversation_ids or row["status"] in TERMINAL:
                continue
            row.update(status="failed", claim_token=None, lease_until=0, finished_at=time.time(), error=reason)
            row.setdefault("claimed_at", None)
            row.setdefault("started_at", None)
            cancelled.append(_append(path, row, "replay_cancelled"))
    return cancelled


def cancel_user_task(root, conversation_id, identifier):
    """Revoke one owner-selected claim; late results cannot acknowledge success."""
    with locked(root) as path:
        row = _read(path).get(identifier)
        if not row or row.get('conversation_id') != conversation_id:
            raise ValueError('Task does not belong to this conversation')
        if row['status'] in TERMINAL:
            return row
        started = bool(row.get('execution_started_at'))
        row.update(status='failed', claim_token=None, lease_until=0, finished_at=time.time(),
                   cancelled_at=time.time(), error='Cancelled by the owner. ' +
                   ('Execution had started; any external effects need separate verification.' if started else
                    'No execution start was recorded.'))
        return _append(path, row, 'owner_cancelled')


def cancel_for_rollback(root, started_at):
    """Keep legacy dispatchers from starting newly accepted or now-held work.

    The release holds web-dispatch admission and has drained active claims.
    Requests and evidence remain durable failed outcomes, never erased/replayed.
    """
    cancelled = []
    with locked(root) as path:
        rows = list(_read(path).values())
        if any(row['status'] in ACTIVE for row in rows):
            raise RuntimeError('Rollback admission cleanup requires drained active tasks')
        for row in rows:
            if row['status'] in TERMINAL:
                continue
            candidate_task = row.get('permission_file') and row['created_at'] >= started_at
            if not candidate_task and not permission_block(root, row):
                continue
            row.update(status='failed', claim_token=None, lease_until=0, finished_at=time.time(),
                       error='Release rollback prevented this pending task from starting under older execution rules. '
                             'The original request is preserved; resubmit it after the release is verified.')
            cancelled.append(_append(path, row, 'release_rollback_cancelled'))
    return cancelled


def abort_admission(root, conversation_id, request_id):
    """Close partial, unclaimed group rows after release admission closes."""
    with locked(root) as path:
        rows = [row for row in _read(path).values() if row.get('conversation_id') == conversation_id
                and (row['request_id'] == request_id or row['request_id'].startswith(request_id + ':'))]
        if any(row['status'] in ACTIVE for row in rows):
            raise RuntimeError('Cannot discard an active admission')
        for row in rows:
            if row['status'] in TERMINAL:
                continue
            row.update(status='failed', claim_token=None, lease_until=0, finished_at=time.time(),
                       error='Release verification interrupted task admission; no worker execution was started.')
            _append(path, row, 'admission_interrupted')

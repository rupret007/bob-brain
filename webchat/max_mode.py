"""Independent max-mode work packages and a durable, single-answer reducer."""
import json
import re
import uuid

import task_queue

MAX_MODE = re.compile(r"\b(?:max[- ]mode|go\s+(?:to\s+)?the\s+max|go\s+all\s+out)\b", re.I)
SUBTASK = re.compile(r"^\s*(?:[-*]|\d+[.)])?\s*\[([\w-]+)\]\s*(.+?)(?=^\s*(?:[-*]|\d+[.)])?\s*\[[\w-]+\]|\Z)", re.M | re.S)
ROLES = {
    "codex": ("Implementation and correctness", "Inspect the implementation and reason through correctness and edge cases. Give concrete findings with evidence."),
    "cursor": ("Integration and tests", "Inspect integration points and test coverage. Identify missing cases and practical validation steps, independently of the correctness review."),
    "claude": ("Design critique", "Critique the design and assumptions using the supplied evidence. Rank the top risks and acceptance criteria. Keep this focused and concise."),
    "gemini": ("Alternatives and scaling", "Analyze alternatives, performance, capacity, and scaling using the supplied evidence. Compare tradeoffs with concrete calculations where possible."),
    "minimax": ("Failure and recovery analysis", "Analyze failure modes, crash recovery, usage limits, and operational observability using the supplied evidence. Give a failure matrix and prioritized remedies."),
    "mini": ("Local test evidence", "Run the local services/test_services.py suite and report its actual output."),
}


def plan(root, prompt, kind):
    """Accept explicit independent packages or expand the standing role split.

    Persist the resulting plan in chat before enqueuing; health changes and
    restarts must never change the membership of an already accepted group.
    """
    goal = MAX_MODE.sub("", prompt).strip(" :,-\n")
    supplied = list(SUBTASK.finditer(goal))
    packages = []
    if supplied:
        context = goal[:supplied[0].start()].strip()
        for match in supplied:
            worker = task_queue.worker_name(match[1].lower())
            if worker == "auto":
                raise ValueError("Max-mode packages need a named worker")
            packages.append(dict(worker=worker, title=ROLES[worker][0],
                                 prompt=context + "\n\nYour independent subtask:\n" + match[2].strip()))
    else:
        path = root / "conductor/lanes.json"
        health = json.loads(path.read_text()) if path.exists() else {}
        available = [lane for lane in task_queue.WORKERS if not health or
                     health.get(lane, {}).get("state") in ("ready", "budget_warning", "busy")]
        # An outage doesn't erase the goal: queue packages and let the scheduler
        # use compatible alternatives as resources recover.
        for worker in available or task_queue.WORKERS:
            title, assignment = ROLES[worker]
            if kind == "coding" and worker == "codex":
                assignment = "Implement the requested production code in your private branch. Own production files only; the independent Cursor package owns tests. Commit changes and report the SHA and verification."
            elif kind == "coding" and worker == "cursor":
                assignment = "Write regression tests for the requested behavior in your private branch. Own test files only; production implementation is a separate package. Commit the tests and report their results against the baseline honestly."
            packages.append(dict(worker=worker, title=title, prompt="Goal:\n" + goal + "\n\nYour independent subtask:\n" + assignment))
    if not 2 <= len(packages) <= 24:
        raise ValueError("Max mode needs between 2 and 24 independent subtasks")
    for package in packages:
        worker = package["worker"]
        package["kind"] = "local" if worker == "mini" else "coding" if kind == "coding" and worker in ("codex", "cursor") else "analysis"
        package["kind"] = task_queue.task_kind(package["kind"], package["prompt"])
        task_queue.validate_worker(worker, package["kind"])
        package["prompt"] += "\n\nComplete only your assigned subtask. Do not start other workers. Distinguish observed evidence from assumptions."
    return goal, packages


def group_id(conversation_id, request_id):
    return "max-" + uuid.uuid5(uuid.NAMESPACE_URL, conversation_id + ":" + request_id).hex


def enqueue(root, conversation_id, intent):
    identifier = group_id(conversation_id, intent["request_id"])
    return [task_queue.enqueue(root, conversation_id, intent["request_id"] + ":" + str(index),
                               package["prompt"], worker=package["worker"], kind=package["kind"],
                               group_id=identifier, group_size=len(intent["subtasks"]), group_index=index,
                               group_goal=intent["goal"], title=package["title"], publish_project=package.get("publish_project"))
            for index, package in enumerate(intent["subtasks"])]


def merge_text(rows):
    """Lossless local reducer: preserves evidence, disagreements and failures.

    No extra provider is required to deliver already completed work after an
    outage. A group is committed as one assistant message by the chat outbox.
    """
    ordered = sorted(rows, key=lambda row: row["group_index"])
    if all(row["status"] == "succeeded" and row.get("publication") for row in ordered):
        return "Pushed " + str(len(ordered)) + " draft branches:\n\n" + "\n".join(
            row["title"] + ": [" + row["publication"]["sha"][:7] + "](" + row["publication"]["url"] + ")."
            for row in ordered)
    succeeded = sum(row["status"] == "succeeded" for row in ordered)
    parts = ["Max mode completed: " + str(succeeded) + "/" + str(len(rows)) + " subtasks succeeded."]
    for row in ordered:
        label = row["title"] + " (" + str(row["worker"] or row["requested_worker"]) + ")"
        body = row.get("result", "") if row["status"] == "succeeded" else "Failed: " + row.get("error", "No result")
        parts.append("### " + label + "\n\n" + body)
    return "\n\n".join(parts)

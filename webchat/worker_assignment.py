"""Turn requests to use LLMs on ongoing work into durable, scoped assignments."""
import json
import re
from pathlib import Path

import task_queue
from api_tasks import ROLES
from build_info import CODE_ROOT, git_checkout_root
from chat_intent import blocked_scopes, command, project_targets, state_for
from live_status_snapshot import observe_work

NAMES = r"(?:gemini|minimax|codex|claude|cursor(?:-agent)?|grok|xai|xAI)"
DIRECTIVE = re.compile(
    r"^(?:remember\s*[:,]?\s*(?:that\s+)?(?:(?:you|we)\s+can\s+|to\s+)?|(?:you|we)\s+can\s+)?"
    r"(?:also\s+)?(?:use|assign|put|have|get|delegate\s+to)\s+(?P<names>" + NAMES +
    r"(?:\s*(?:,|&|and)\s*(?:and\s+)?" + NAMES + r")*)\b(?P<rest>.*)$", re.I | re.S)
ONGOING = re.compile(r"\b(?:ongoing|current|existing|active|running|queued)\b.{0,35}\b(?:jobs?|tasks?|work|projects?)\b|"
                     r"\b(?:jobs?|tasks?|work|projects?)\b.{0,30}\b(?:ongoing|underway|running)\b|"
                     r"\b(?:for|on|with)\s+(?:these|those|our|the)\s+(?:jobs?|tasks?|work)\b", re.I)


def requested_workers(text, conversation=None):
    cleaned = command(text)
    if re.match(r"^(?:don't|do not|never|stop|hold)\b", cleaned, re.I):
        return None
    # A follow-up references the last explicit worker request, not arbitrary
    # names from a model answer or provider-health metadata.
    followup = re.search(r"\b(?:add|assign|queue|give)\s+(?:some |more |new )?(?:work|jobs?|tasks?)\s+(?:for|to)\s+(?:them|those (?:LLMs|workers))\b|"
                         r"\b(?:want|need)\s+them\s+(?:workout|working|to work|busy)\b|"
                         r"\b(?:put|get|keep)\s+them\s+(?:to work|working|busy)\b", cleaned, re.I)
    if followup:
        names = (conversation or {}).get("assignment_workers")
        if not names:
            for message in reversed((conversation or {}).get("messages", [])):
                if message.get("role") == "user" and message.get("content") != text:
                    names = requested_workers(message.get("content", ""))
                    if names:
                        break
        if names:
            return list(names)
    all_workers = re.match(r"^(?:use|assign|put|get|keep)\s+all\s+(?:the\s+)?(?:LLMs|models|workers)\b", cleaned, re.I)
    if all_workers and (ONGOING.search(cleaned) or re.search(r"\b(?:to work|busy|working)\b", cleaned, re.I)):
        return list(task_queue.MODEL_WORKERS)
    match = DIRECTIVE.match(cleaned)
    reminder = re.match(r"^(?:remember|you can|we can)\b", cleaned, re.I)
    if not match or not (ONGOING.search(match["rest"]) or (reminder and re.fullmatch(r"\s*(?:too|also)?[.!]*", match["rest"], re.I))):
        return None
    return list(dict.fromkeys(name.lower().replace("cursor-agent", "cursor")
                              for name in re.findall(NAMES, match["names"], re.I)))


def issue_followup(root, conversation, text):
    if not re.fullmatch(r"if you find (?:any )?(?:issues|bugs)[, ]+(?:please )?fix them[.!]*", command(text), re.I):
        return None
    previous = next((m["dispatch_intent"] for m in reversed(conversation["messages"][:-2])
                     if m.get("dispatch_intent", {}).get("worker_assignment")), None)
    if not previous or not previous.get("assignment_projects"):
        return None
    project = previous["assignment_projects"][0]
    return ("Fix verified issues in " + project + "\nInspect the ongoing work and available review reports, "
            "reproduce a concrete issue, implement one bounded fix if warranted, and run relevant tests. "
            "Report evidence if no fix is needed. Work in your assigned draft worktree; never deploy or merge.")


def deployed_project_context(root):
    """A pinned checkout can supply API evidence, never proof of ongoing work."""
    # Deployments can have no active jobs and no identifiable project screen.
    # Both services must select this running checkout; an arbitrary/stale pin
    # or a rollback copy without Git evidence is not enough to assign a report.
    try:
        for name in ("webchat", "dispatch"):
            value = (root / "conductor/state" / (name + "-code-root")).read_text().strip()
            path = Path(value)
            if not path.is_absolute() or path.resolve(strict=True) != CODE_ROOT:
                return None
    except (OSError, ValueError, RuntimeError):
        return None
    if git_checkout_root(CODE_ROOT) is None:
        return None
    return dict(id=None, project="Web Bob", context="project context", prompt=(
        "The Web Bob checkout is selected by matching deployment pins for this server and its dispatcher; "
        "no current task or worker execution is confirmed. Inspect the supplied repository snapshot for "
        "concrete dispatch findings and regression test drafts, including webchat/build_info.py, "
        "webchat/worker_assignment.py, "
        "webchat/task_dispatch.py, state/task_queue.py and services/dispatch_worker.py. "
        "Do not infer active work, progress or results from deployment metadata."))


def plan(root, conversation, text, workers):
    for worker in workers:
        task_queue.worker_name(worker)  # Reject Grok/xAI before any queue write.
    observed = observe_work(root)
    state = state_for(conversation)
    targets = project_targets(text, state)
    candidates = []
    for row in observed["records"].values():
        if (row.get("status") or row.get("state")) not in ("queued", "claimed", "launched", "running"):
            continue
        if row.get("source_job_id") or (row.get("kind") in ("audit", "test-writing", "planning", "review", "research", "eval-grading")):
            continue  # Never recursively create report jobs about report jobs.
        prompt = row.get("prompt") or row.get("title") or row.get("project")
        if not prompt:
            continue
        names = project_targets(row.get("project") or prompt, state)
        if targets and not any(name in targets for name in names):
            continue
        if blocked_scopes(state, names):
            continue
        candidates.append(dict(id=row["job_id"], prompt=prompt,
                               project=", ".join(names) or "Web Bob"))
    # Some ongoing jobs are external CLI workers, observed outside the journal.
    known = {row["id"] for row in candidates}
    for row in observed["work"]:
        if row["state"] != "running" or row.get("job_id") in known or not (row.get("task") or row.get("title")) or not row.get("project"):
            continue
        if row.get("job_id") and observed["records"].get(row["job_id"], {}).get("kind") in ("audit", "test-writing", "planning", "review", "research", "eval-grading"):
            continue
        if targets and row["project"] not in targets:
            continue
        if blocked_scopes(state, [row["project"]]):
            continue
        task = row.get("task") or ("Observed active lane: " + row["title"] +
                                   ". Its original task prompt was not recorded; inspect the project's current code and "
                                   "state that limitation. Do not invent the lane's exact assignment.")
        candidates.append(dict(id=None, prompt=task, project=row["project"]))
    # An open project lane can outlive its worker process. It still identifies
    # a repository for a new API report, but proves neither an ongoing task nor
    # execution. Use it only when no permitted active assignment is available;
    # never turn this limited context into a coding job or a fake source job ID.
    if not candidates and all(worker in task_queue.API_WORKERS for worker in workers):
        seen_projects = set()
        for row in observed["work"]:
            project = row.get("project")
            if (row["state"] != "unverified" or row.get("source") != "screen" or row.get("job_id")
                    or row.get("screen") not in observed.get("sessions", {})
                    or not project or not row.get("repo") or not row.get("title") or project in seen_projects):
                continue
            if (targets and project not in targets) or blocked_scopes(state, [project]):
                continue
            context = ("Observed open project lane: " + row["title"] + ". Its worker activity is unverified; "
                       "no current task is confirmed. Inspect the project's supplied repository snapshot "
                       "for concrete findings and regression test drafts. Do not infer active work, "
                       "progress or results from the lane name or historical logs.")
            candidates.append(dict(id=None, prompt=context, project=project, context="project context"))
            seen_projects.add(project)
        if not candidates and (not targets or "Web Bob" in targets) and not blocked_scopes(state, ["Web Bob"]):
            context = deployed_project_context(root)
            if context:
                candidates.append(context)
    if not candidates:
        raise ValueError("I couldn't assign those workers: there is no identifiable ongoing job permitted by the current holds. Name a project and task to start.")
    health = root / "conductor/lanes.json"
    board = json.loads(health.read_text()) if health.exists() else {}
    packages = []
    for index, worker in enumerate(workers):
        row = board.get(worker, {})
        if row.get("state") in ("needs_key", "unavailable", "budget_exhausted", "cooldown", "needs_login"):
            raise ValueError("I couldn't assign " + worker + ": " + row["state"].replace("_", " ") + ". No new assignments were queued.")
        source = candidates[index % len(candidates)]
        kind, role = ROLES.get(worker, ("analysis", "Review the ongoing task and propose next steps"))
        context = source.get("context", "ongoing task")
        # One concrete bounded package per requested worker. Keep existing
        # coders running; do not revoke a live claim or share their edit rights.
        prompt = ("Project: " + source["project"] + "\nYour independent subtask:\n" + role +
                  " for the following " + context + ". Deliver concrete findings and an actionable plan. " +
                  ("Also deliver actual regression test drafts with inputs, triggers and expected assertions. "
                   if kind == "test-writing" else "") +
                  "Never deploy or resolve conflicts.\n" +
                  context.capitalize() + ":\n" + source["prompt"][:8000])
        if source["project"] == "Web Bob":
            prompt += ("\nRelevant evidence: services/dispatch_worker.py, services/result_acceptance.py, "
                       "services/test_result_acceptance.py, services/test_api_workers.py, "
                       "state/task_queue.py, webchat/worker_assignment.py, webchat/test_dispatch.py. "
                       "Inspect these supplied files before proposing dispatch/completion regressions.")
        packages.append(dict(worker=worker, kind=kind, title=source["project"] + " — " + role,
                             prompt=prompt, source_job_id=source["id"]))
    return packages

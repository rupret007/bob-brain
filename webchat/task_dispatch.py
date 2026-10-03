"""Chat task submission and durable result delivery, independent of chat models."""
from __future__ import annotations

import copy
import json
import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "state"))
import task_queue
import max_mode
from api_tasks import normalize_kind
from chat_intent import (POLITE, PREAMBLE, PUSH, blocked_scopes, command, hold_reply,
                         project_targets, projects, PROJECT, PROJECT_NAMES, state_for, normalize_projects, project_start)

WORK = re.compile(
    r"^" + POLITE +
    r"(?:plan|grade|score|evaluate|review|analy[sz]e|audit|research|investigate|inspect|check|compare|summari[sz]e|calculate|"
    r"read|open|save|append|write|draft|create|build|implement|fix|repair|debug|test|trace|update|refactor|add|remove|"
    r"diagnose|figure out|find out|look into|work on|improve|make)\b.*", re.I | re.S)
ROUTED = re.compile(r"^" + POLITE + r"(?:have|get|ask|use|assign(?:\s+to)?|delegate(?:\s+to)?)\s+"
                    r"(codex|claude|cursor-agent|cursor|gemini|minimax|mini|grok)\b\s*(?:to\b|[:,])?\s*(.*)$", re.I | re.S)
PREFIX = re.compile(r"^(?:worker\s*[:=]\s*)?(codex|claude|cursor-agent|cursor|gemini|minimax|mini|grok)\s*:\s*(.+)$", re.I | re.S)
CODING = re.compile(r"\b(?:fix|repair|improve|implement|refactor|debug|build|run|execute|install|edit|change|modify)\b|"
                    r"\b(?:write|add|create|update|remove)\b.{0,60}\b(?:code|file|test|function|service|script|app|feature|database|schema)\b", re.I | re.S)
PROJECT_LIST = PROJECT.pattern + r"(?:\s*(?:,|&|\band\b|\bthen\b)\s*(?:and\s+)?" + PROJECT.pattern + r")*"
FOLLOW_UP = re.compile(r"^" + POLITE + r"(?:go(?: ahead)?|resume|do it|handle it|yes(?: please)?|let['’]s do it|"
                       r"(?:go(?: ahead)?|resume)\s+(?:(?:with|on)\s+)?" + PROJECT_LIST + r")[.!?]*$", re.I)
CHAT_STYLE = re.compile(r"^" + POLITE + r"(?:keep|make)\s+(?:your\s+)?(?:replies|answers|responses)\s+"
                        r"(?:short(?:er)?|brief(?:er)?|concise|friendly|friendlier|plain(?:er)?|natural)\b", re.I)
PROPOSAL = re.compile(r"^(?:I can|I could|Happy to|Shall I|Want me to|Would you like me to)\s+(.+?)[.!?]*$", re.I)


def needs_task_detail(prompt):
    """A verb or a bare reference is not enough to start work."""
    prompt = PREAMBLE.sub("", prompt.strip()).strip(" .!?:")
    prompt = re.sub(r"^" + POLITE, "", prompt, flags=re.I)
    prompt = re.sub(r"^(?:figure out|find out|look into|work on|\w+)\b\s*", "", prompt, count=1, flags=re.I)
    return not prompt or bool(re.fullmatch(r"(?:(?:on|to|do)\s+)?(?:it|this|that|something|anything|the task|the job)", prompt, re.I))


def followup_work(conversation):
    """Resolve only a current saved proposal, never an old or completed task."""
    recent = conversation["messages"][-2:]
    text = recent[0].get("content", "") if recent and recent[0].get("role") == "user" else ""
    scopes = projects(text) if FOLLOW_UP.fullmatch(PREAMBLE.sub("", text)) else []

    def matches_scope(prompt):
        if not scopes:
            return True
        targets = project_targets(prompt, state_for(conversation))
        return bool(targets) and all(name in scopes for name in targets)

    if conversation.get("held_job"):
        job = conversation["held_job"]
        if matches_scope(job["prompt"]):
            return job["prompt"], job["worker"]
    if conversation.get("pending_job"):
        prompt = conversation["pending_job"]
        work, worker = parse_work(prompt)
        if matches_scope(work or prompt):
            return work or prompt, worker
    # submit() has already appended the new user turn and its reply placeholder.
    previous = conversation["messages"][:-2]
    if not previous:
        return None, "auto"
    last = previous[-1]
    if last.get("role") != "assistant" or last.get("status") != "done" or last.get("action_card") or last.get("task_id"):
        return None, "auto"
    text = last.get("content", "").strip()
    text = re.sub(r"\s*(?:[.!]|[—–])\s*(?:want me to|shall I|should I)(?:\s+(?:go ahead|start|do (?:it|that)|prep a review job for it))?\?\s*$", "", text, flags=re.I)
    text = re.sub(r"\s*(?:[.!]|[—–])\s*(?:just\s+)?(?:say go|say the word)\b[^\n]*$", "", text, flags=re.I)
    proposal = PROPOSAL.fullmatch(text)
    if not proposal or re.search(r"\bor\b|\n|[.!?]\s", proposal[1], re.I):
        return None, "auto"
    prompt = re.sub(r"^(?:offer to|help(?: you)?(?: to)?)\s+", "", proposal[1], flags=re.I)
    prompt = re.sub(r"^take a look at\b", "review", prompt, flags=re.I)
    prompt = re.sub(r"\s+(?:whenever you want|when(?:ever)? you['’]re ready)$", "", prompt, flags=re.I)
    return parse_work(prompt) if matches_scope(prompt) else (None, "auto")


def parse_work(text, *, conversation=None):
    text = PREAMBLE.sub("", text.strip())
    if CHAT_STYLE.match(text):
        return None, "auto"
    if project_start(text):
        return text.strip(), "auto"
    if PUSH.match(command(text)):
        return text.strip(), "auto"
    if max_mode.MAX_MODE.search(text) and (WORK.match(text) or max_mode.MAX_MODE.match(command(text))):
        return text.strip(), "max"
    lane = re.fullmatch(r"(?:start|run)\s+(?:a\s+)?lane\s+(codex|cursor-agent|cursor|claude|gemini|minimax|grok)\s*:\s*(.+)", text.strip(), re.I | re.S)
    if lane:
        return lane[2].strip(), lane[1].lower()
    routed = (ROUTED.match(text.strip()) or PREFIX.match(text.strip()) or
              re.match(r"^" + POLITE + r"(codex|claude|cursor-agent|cursor|gemini|minimax|mini|grok)\s+"
                       r"((?:plan|grade|score|evaluate|review|audit|inspect|fix|build|write|research)\b.+)$", text.strip(), re.I | re.S))
    if routed:
        return routed.group(2).strip(), routed.group(1).lower()
    from answer_intent import implementation_deliverable
    request = re.sub(r"^" + POLITE, "", text.strip(), flags=re.I)
    target_request = WORK.match(request) or re.match(r'^(?:prepare|produce|put together)\b', request, re.I)
    if target_request and (task_queue.file_task_kind(request) or implementation_deliverable(request)):
        return text.strip(), 'auto'
    if conversation and conversation.get('answer_focus', {}).get('origin'):
        from conversation_focus import correction
        from answer_intent import requires_execution, requires_research
        request = command(text)
        if (correction(request) and not task_queue.file_task_kind(request)
                and not requires_execution(request) and not requires_research(request)):
            # A reference to the current answer stays an answer regardless of
            # its artifact noun (notice, invitation, note, paragraph, etc.).
            return None, 'auto'
    if WORK.match(text.strip()):
        from answer_intent import wants_answer
        # Worker choice, max mode, project controls, and explicit file targets
        # retain their existing execution paths. A requested poem, comparison,
        # explanation, or plan is otherwise the answer itself, not a job.
        request = re.sub(r"^" + POLITE, "", text.strip(), flags=re.I)
        if wants_answer(request) and not task_queue.file_task_kind(request):
            return None, "auto"
        return text.strip(), "auto"
    return None, "auto"


def task_receipt(row):
    from worker_evidence import clean
    names = {"codex": "Codex", "claude": "Claude", "cursor": "Cursor", "gemini": "Gemini", "minimax": "MiniMax", "mini": "mini"}
    worker = row["requested_worker"]
    target = names[worker] if worker != "auto" else "the next available worker"
    title = row.get("title") or row.get("prompt", "the requested task").splitlines()[0]
    title = clean(title, 100).strip(" .?!") or "the requested task"
    return "I queued “" + title + "” for " + target + " (job `" + row["id"] + "`)."


def task_kind(prompt):
    # Politeness doesn't change whether the requested work needs file tools.
    prompt = re.sub(r"^" + POLITE, "", PREAMBLE.sub("", prompt.strip()), flags=re.I)
    if task_queue.file_request(prompt):
        return "artifact"
    # Required output literals (for example a verification marker containing
    # 'FIX') describe the answer, not an instruction to change code.
    prompt = re.sub(r"\b(?:include|contain|use|return|say)\s+(?:the\s+)?exact\s+(?:phrase|text|string|words)\s*:?\s*"
                    r"(['\"`])(.+?)\1", "", prompt, flags=re.I)
    file_kind = task_queue.file_task_kind(prompt)
    if file_kind:
        return file_kind
    from answer_intent import requires_execution, requires_research, implementation_deliverable
    if requires_execution(prompt) or implementation_deliverable(prompt):
        return 'coding'
    if requires_research(prompt):
        return 'research'
    # An analysis of code is still analysis; actual edits/execution need a CLI.
    if re.search(r"\bread[- ]only\b", prompt, re.I) and re.search(r"\b(?:review|audit|analysis|inspection)\b", prompt, re.I):
        return "analysis"
    if re.match(r"^(?:please\s+)?(?:review|analy[sz]e|audit|compare|summari[sz]e|research|draft|calculate)\b", prompt, re.I):
        return "analysis"
    return "coding" if CODING.search(prompt) else "analysis"


def project_plan(root, description, names, worker):
    """One independently routable job per project, using existing capabilities."""
    goal = max_mode.MAX_MODE.sub("", description).strip(" :,-\n")
    starting = project_start(description)
    improve = bool(starting or PUSH.match(command(description)) or (max_mode.MAX_MODE.match(command(description)) and not WORK.match(goal)))
    publish = bool(re.fullmatch(r"push\s+" + PROJECT_LIST + r"[.!]*", command(description), re.I))
    kind = normalize_kind(worker, "coding" if improve else task_kind(goal), goal)
    eligible = task_queue.worker_order(kind)
    if worker != "auto":
        task_queue.validate_worker(worker, kind)
        eligible = (worker,)
    board = root / "conductor/lanes.json"
    health = json.loads(board.read_text()) if board.exists() else {}
    ready = [lane for lane in eligible if not health or health.get(lane, {}).get("state") in ("ready", "budget_warning")]
    candidates = ready or list(eligible)
    rows = list(task_queue.tasks(root).values())
    load = {}
    for lane in candidates:
        observed = sum(row["status"] in task_queue.ACTIVE and row["worker"] == lane for row in rows)
        reserved = max(observed, health.get(lane, {}).get("active", 0))
        if health.get(lane, {}).get("state") == "busy":
            reserved = max(reserved, task_queue.capacity(lane))
        load[lane] = reserved + sum(row["status"] == "queued" and row["requested_worker"] == lane for row in rows)
    packages = []
    for project in names:
        lane = min(candidates, key=lambda candidate: load[candidate] / task_queue.capacity(candidate))
        load[lane] += 1
        # The existing worker chooses its repository from the prompt. Never
        # include the other projects' names in this project's assignment.
        scoped = PROJECT.sub(lambda match: project if projects(match[0]) == [project]
                             else "another project", normalize_projects(description))
        assignment = ("Improve " + project + ": inspect the project, choose one useful bounded fix, implement it, and run relevant tests."
                      if improve else "Carry out this request for " + project + " only.")
        prompt = ("Project: " + project + "\n" + assignment + "\nJeff's request: " + scoped +
                  ("\nReturn a report or proposed patch for this project; the server saves it under reviews/. "
                   "Never deploy, apply changes or resolve conflicts. " if lane in task_queue.API_WORKERS else
                   "\nWork only on this project in your assigned worktree and draft branch. Report actual results. ") +
                  "Never merge, undraft, force-push, use Grok/xAI, send texts, or start other workers.")
        if project == "Fantasy Football":
            prompt += "\nESPN access is read-only. Jeff makes all lineup and roster moves himself."
        packages.append(dict(worker=lane, kind=kind, title=project, prompt=prompt,
                             publish_project=project if publish or starting else None, draft_pr=starting))
    return packages


def project_receipt(rows):
    return "\n".join(task_receipt(row) for row in sorted(rows, key=lambda row: row.get("group_index") or 0))


def result_receipt(row):
    """Keep full evidence in the authenticated Jobs result, not a chat dump."""
    from worker_activity import WORKER_NAMES
    from worker_evidence import clean
    worker = WORKER_NAMES.get(row.get("worker") or row.get("requested_worker"), "The worker")
    title = clean(row.get("title") or row["prompt"].splitlines()[0], 100).strip(" .?!")
    succeeded = row["status"] == "succeeded"
    body = row.get("result") if succeeded else row.get("error")
    # A completed API report is an artifact, not a new dispatch or an executed
    # patch. Cite the saved report instead of reprinting model instructions.
    if succeeded and row.get("result_path"):
        summary = "report saved"
    else:
        body = (body or "No result text was recorded").strip()
        line = next((line.strip().lstrip("# ") for line in body.splitlines() if line.strip()), "")
        sentence = re.split(r"[.!?](?:\s|$)", line, maxsplit=1)[0]
        summary = clean(sentence, 180).strip(" .?!")
        from dispatch_receipts import claims_dispatch
        if claims_dispatch(summary):
            summary = "verified result saved" if succeeded else "the task failed; see the saved error"
    lead = (worker + " finished “" + title + "”" if succeeded else
            "“" + title + "” failed after " + str(row.get("attempts", 0)) + " attempts on " + worker)
    return (lead + " (job `" + row["id"] +
            "`): " + summary + "; [full result](/api/jobs/result?id=" + row["id"] + ").")


def group_result_receipt(rows, label):
    ordered = sorted(rows, key=lambda row: row["group_index"])
    if all(row["status"] == "succeeded" and row.get("publication") for row in ordered):
        return max_mode.merge_text(ordered, label)
    succeeded = sum(row["status"] == "succeeded" for row in ordered)
    return (label + " completed: " + str(succeeded) + "/" + str(len(ordered)) + ".\n" +
            "\n".join(result_receipt(row) for row in ordered))


class TaskDispatch:
    def paused_dispatch_reply(self, conversation):
        """Keep solo maintenance safe without ending a real request at a dead end."""
        if not (self.root / 'conductor/SOLO-WORKER').exists():
            return None
        message = conversation['messages'][-1]
        message['dispatch_blocked'] = (
            "Additional project workers are disabled by the current solo Codex setting. "
            "This request did not start or queue them, and no provider restriction was applied. "
            "Web Bob chat can still help with the requested work here.")
        self.save(conversation)
        self.conversations[conversation['id']] = conversation
        self.launch(conversation['id'])
        return self.public(conversation)

    def submit_council(self, conversation, topic, request_id):
        # Council has the same journal and receipt contract as every other job.
        description = ("max-mode Council: " + topic + "\n"
                       "[gemini] Audit the evidence for this council question: " + topic + "\n"
                       "[minimax] Draft test cases and failure checks for this council question: " + topic + "\n"
                       "[claude] Review the design and assumptions for this council question: " + topic)
        return self.submit_max_task(conversation, description, request_id)

    def submit_worker_assignment(self, conversation, description, request_id, workers):
        from worker_assignment import plan
        if conversation.get('answer_focus'):
            conversation['answer_focus'].update(origin=None, corrections=[])
        message = conversation["messages"][-1]
        try:
            if self.ledger_root(conversation["id"]) != self.root:
                raise ValueError("Worker dispatch is disabled in a drill overlay.")
            paused = self.paused_dispatch_reply(conversation)
            if paused is not None:
                return paused
            if (self.root / "conductor/MAINTENANCE").exists():
                raise ValueError("Scheduling is paused for maintenance; no assignments were queued.")
            packages = plan(self.root, conversation, description, workers)
        except ValueError as exc:
            return self.intent_reply(conversation, str(exc))
        conversation["assignment_workers"] = list(workers)
        intent = dict(prompt=description, request_id=request_id, goal=description,
                      worker_assignment=True, project_batch=True,
                      assignment_projects=list(dict.fromkeys(name for package in packages
                                               for name in projects(package["prompt"].splitlines()[0]))))
        if len(packages) > 1:
            intent["subtasks"] = packages
        else:
            intent.update(packages[0])
        message.update(status="done", content="Saving worker assignments…", dispatch_intent=intent)
        self.save(conversation)
        self.conversations[conversation["id"]] = conversation
        self.reconcile_tasks()
        return self.public(self.conversations[conversation["id"]])

    def cancel_task_turn(self, conversation, text):
        directive = command(text)
        match = re.fullmatch(r'(?:cancel|stop)\s+(?:(?:that|this|the|current|last)\s+)?(?:task|job|work)'
                             r'(?:\s+(webchat-[a-f0-9]{32}))?[.!]*', directive, re.I)
        if not match:
            return None
        rows = [row for row in task_queue.tasks(self.root).values()
                if row.get('conversation_id') == conversation['id']]
        selected = next((row for row in rows if row['id'] == match[1]), None) if match[1] else max(rows, key=lambda row:row['created_at'], default=None)
        if selected is None:
            return self.intent_reply(conversation, 'There is no matching task in this conversation to cancel.')
        row = task_queue.cancel_user_task(self.root, conversation['id'], selected['id'])
        if row.get('cancelled_at'):
            content = ('Cancellation recorded for `' + row['id'] + '`. No further start or successful result '
                       'will be accepted for this task. ' +
                       ('Execution had begun; existing effects are not undone.' if row.get('execution_started_at') else
                        'No execution start was recorded.'))
        else:
            content = 'That task already finished with state ' + row['status'] + '; cancellation cannot undo its effects.'
        return self.intent_reply(conversation, content)

    def submit_max_task(self, conversation, description, request_id):
        return self.submit_task(conversation, description, request_id, worker="max")

    def submit_task(self, conversation, description, request_id, worker="auto", *, expected_code_identity=None, attempt_limit=None):
        from app import hard_rule_refusal
        if conversation.get('answer_focus'):
            conversation['answer_focus'].update(origin=None, corrections=[])
        identifier = conversation["id"]
        message = conversation["messages"][-1]
        # parse_start's normalized lane description preserves routing across
        # both the legacy queue and the durable dispatcher.
        lane = re.match(r"Lane: (codex|cursor-agent|cursor|claude|gemini|minimax|grok)\n(.+)", description, re.S)
        if lane:
            worker, description = lane[1], lane[2]
        routed_prompt, routed_worker = parse_work(description)
        if routed_worker != "auto":
            description, worker = routed_prompt, routed_worker
        held = conversation.get('held_job') or {}
        if held.get('prompt') == description and held.get('worker') == worker:
            if attempt_limit is None:
                attempt_limit = held.get('attempt_limit')
            if expected_code_identity is None:
                expected_code_identity = held.get('expected_code_identity')
        state = state_for(conversation)
        names = project_targets(description, state)
        scopes = blocked_scopes(state, names)
        if scopes:
            conversation["held_job"] = dict(prompt=description, worker=worker)
            if attempt_limit is not None:
                conversation['held_job']['attempt_limit'] = attempt_limit
            if expected_code_identity is not None:
                conversation['held_job']['expected_code_identity'] = expected_code_identity
            message.update(status="done", provider="dispatcher", content=hold_reply(scopes))
            self.save(conversation)
            self.conversations[identifier] = conversation
            return self.public(conversation)
        try:
            task_queue.validate_attempt_limit(attempt_limit)
            publish_project = None
            draft_pr = False
            maximum = worker == "max"
            project_batch = len(names) >= 2
            if attempt_limit is not None and (maximum or project_batch):
                raise ValueError("An attempt limit requires a single task, not a task group")
            worker = "auto" if maximum else task_queue.worker_name(worker)
            kind = task_kind(max_mode.MAX_MODE.sub("", description).strip(" :,-\n") if maximum else description)
            kind = normalize_kind(worker, kind, description)
            if not maximum:
                task_queue.validate_worker(worker, "local" if worker == "mini" else kind)
            refusal = hard_rule_refusal(description)
            if refusal:
                raise ValueError(refusal)
            if self.ledger_root(identifier) != self.root:
                raise ValueError("Worker dispatch is disabled in a drill overlay. Use a normal conversation.")
            if (self.root / 'conductor/locks/webbob-activation.json').exists():
                raise ValueError('Release verification is in progress. No task was queued; your request remains saved in this conversation.')
            paused = self.paused_dispatch_reply(conversation)
            if paused is not None:
                return paused
            if (self.root / "conductor/MAINTENANCE").exists():
                raise ValueError("Scheduling is paused for maintenance; this task was not queued.")
            if project_batch:
                goal, subtasks = description, project_plan(self.root, description, names, worker)
                kind = subtasks[0]["kind"]
            elif names and (PUSH.match(command(description)) or project_start(description)):
                package = project_plan(self.root, description, names, worker)[0]
                description, worker, kind = package["prompt"], package["worker"], package["kind"]
                publish_project = package.get("publish_project")
                draft_pr = package.get("draft_pr", False)
            elif maximum:
                goal, subtasks = max_mode.plan(self.root, description, kind)
        except ValueError as exc:
            message.update(status="done", content=str(exc), action_card={"state": "refused", "executable": False})
            self.save(conversation)
            self.conversations[identifier] = conversation
            return self.public(conversation)
        # Save the originating message AND intent before the queue side effect.
        # Startup/reconciliation retries this idempotently after either write fails.
        intent = dict(prompt=description, worker=worker, kind=kind, request_id=request_id, publish_project=publish_project, draft_pr=draft_pr)
        if expected_code_identity:
            intent['expected_code_identity'] = expected_code_identity
        if attempt_limit is not None:
            intent['attempt_limit'] = attempt_limit
        if maximum or project_batch:
            intent.update(goal=goal, subtasks=subtasks)
        if project_batch:
            intent["project_batch"] = True
        held = conversation.get("held_job")
        if held and not blocked_scopes(state, project_targets(held["prompt"], state)):
            conversation.pop("held_job", None)
        message.update(status="done", content="Saving your task for a worker…", dispatch_intent=intent)
        self.save(conversation)
        self.conversations[identifier] = conversation
        self.reconcile_tasks()
        return self.public(self.conversations[identifier])

    def reconcile_tasks(self):
        with self.lock:
            if self.closing.is_set():
                return
            for identifier, current in list(self.conversations.items()):
                value = copy.deepcopy(current)
                changed = False
                for message in value["messages"]:
                    intent = message.get("dispatch_intent")
                    if not intent or message.get("task_id") or message.get("group_id"):
                        continue
                    state = state_for(value)
                    scopes = blocked_scopes(state, intent.get("assignment_projects", project_targets(intent["prompt"], state)))
                    if scopes:
                        content = hold_reply(scopes)
                        if message["content"] != content:
                            message["content"] = content
                            changed = True
                        continue
                    try:
                        if intent.get("subtasks"):
                            rows = max_mode.enqueue(self.root, identifier, intent,
                                                    permission_file=self.state / (identifier + '.json'))
                            group = rows[0]["group_id"]
                            message.update(group_id=group, task_ids=[row["id"] for row in rows], status="done", provider="dispatcher",
                                           content=project_receipt(rows),
                                           action_card={"id": message["request_id"], "state": "queued", "executable": False,
                                                        "group_id": group, "queue_id": group, "goal_text": intent["goal"][:160]})
                            from dispatch_receipts import verify_saved_receipt
                            verify_saved_receipt(self.root, value, message)
                            changed = True
                            continue
                        row = task_queue.enqueue(self.root, identifier, intent["request_id"], intent["prompt"],
                                                 worker=intent["worker"], kind=intent["kind"], publish_project=intent.get("publish_project"),
                                                 draft_pr=intent.get("draft_pr", False), title=intent.get("title"),
                                                 source_job_id=intent.get("source_job_id"),
                                                 permission_file=self.state / (identifier + '.json'),
                                                 project_scopes=intent.get('assignment_projects') or project_targets(intent['prompt'], state),
                                                 expected_code_identity=intent.get('expected_code_identity'),
                                                 attempt_limit=intent.get('attempt_limit'))
                        message.update(task_id=row["id"], status="done", provider="dispatcher",
                                       content=task_receipt(row),
                                       action_card={"id": message["request_id"], "state": "queued", "executable": False,
                                                    "queue_id": row["id"], "task_id": row["id"], "goal_text": row["prompt"][:160]})
                        from dispatch_receipts import verify_saved_receipt
                        verify_saved_receipt(self.root, value, message)
                        changed = True
                    except task_queue.AdmissionPaused as exc:
                        task_queue.abort_admission(self.root, identifier, intent['request_id'])
                        message['blocked_dispatch_intent'] = message.pop('dispatch_intent')
                        message.update(status='done', provider='dispatcher', content=str(exc) +
                                       ' The original task remains saved; retry it when release verification finishes.',
                                       action_card={'state':'refused', 'executable':False})
                        changed = True
                if changed:
                    self.save(value)
                    self.conversations[identifier] = value
            all_rows = list(task_queue.tasks(self.root).values())
            by_id = {row["id"]: row for row in all_rows}
            for identifier, current in list(self.conversations.items()):
                value = copy.deepcopy(current)
                changed = False
                for message in value["messages"]:
                    if not message.get("dispatch_intent", {}).get("project_batch") or not message.get("task_ids"):
                        continue
                    members = [by_id[task_id] for task_id in message["task_ids"]]
                    tasks = [{key: row.get(key) for key in ("id", "worker", "status")} for row in members]
                    card = message.get("action_card", {})
                    if card.get("tasks") != tasks:
                        card["tasks"] = tasks
                        if all(row["status"] in task_queue.TERMINAL for row in members):
                            card["state"] = "done" if all(row["status"] == "succeeded" for row in members) else "blocked"
                        elif any(row["status"] == "running" for row in members):
                            card["state"] = "running"
                        elif any(row["status"] == "claimed" for row in members):
                            card["state"] = "claimed"
                        else:
                            card["state"] = "queued"
                        # The receipt is an event at created_at, not a mutable
                        # status field. Completion gets its own dated message.
                        changed = True
                if changed:
                    self.save(value)
                    self.conversations[identifier] = value
            self.reconcile_groups(all_rows)
            for row in all_rows:
                if row.get("group_id"):
                    continue
                identifier = row["conversation_id"]
                if identifier in self.conversations and row["status"] in task_queue.ACTIVE:
                    value = copy.deepcopy(self.conversations[identifier])
                    changed = False
                    for message in value["messages"]:
                        if message.get("task_id") == row["id"] and message.get("action_card"):
                            card = message["action_card"]
                            if (card.get("state"), card.get("worker")) != (row["status"], row["worker"]):
                                card.update(state=row["status"], worker=row["worker"])
                                changed = True
                    if changed:
                        self.save(value)
                        self.conversations[identifier] = value
                if row["status"] not in task_queue.TERMINAL or row.get("delivered_at") or identifier not in self.conversations:
                    continue
                value = copy.deepcopy(self.conversations[identifier])
                # Ordinary model replies still address the last message. Wait
                # until they finish before appending an asynchronous task result.
                if identifier in self.workers or (value["messages"] and value["messages"][-1]["status"] == "waiting"):
                    continue
                message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, row["id"] + ":result"))
                if not any(m["id"] == message_id for m in value["messages"]):
                    success = row["status"] == "succeeded"
                    content = result_receipt(row)
                    value["messages"].append(dict(id=message_id, request_id=row["request_id"], task_id=row["id"],
                                                  role="assistant", status="done", provider=row["worker"],
                                                  content=self.redact(content), created_at=time.time(),
                                                  task_status=row["status"], claimed_at=row.get("claimed_at"),
                                                  started_at=row.get("started_at"), finished_at=row["finished_at"]))
                    for message in value["messages"]:
                        if message.get("task_id") == row["id"] and message.get("action_card"):
                            message["action_card"].update(state="done" if success else "blocked", worker=row["worker"])
                    self.save(value)  # Commit the answer BEFORE acknowledging outbox delivery.
                    self.conversations[identifier] = value
                import alignment_events
                try:
                    alignment_events.record_task_result(self.root, row, self.redact)
                except OSError:
                    # The conversation result is already durable. Leave this
                    # outbox item pending so recovery retries only publication.
                    continue
                task_queue.delivered(self.root, row["id"], message_id)

    def reconcile_groups(self, rows):
        groups = {}
        for row in rows:
            if row.get("group_id"):
                groups.setdefault(row["group_id"], []).append(row)
        for group, members in groups.items():
            first = members[0]
            identifier = first["conversation_id"]
            if (not task_queue.group_complete(members) or any(r["status"] not in task_queue.TERMINAL for r in members)
                    or all(r.get("delivered_at") for r in members) or identifier not in self.conversations):
                continue
            value = copy.deepcopy(self.conversations[identifier])
            if identifier in self.workers or (value["messages"] and value["messages"][-1]["status"] == "waiting"):
                continue
            message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, group + ":result"))
            if not any(m["id"] == message_id for m in value["messages"]):
                success = all(row["status"] == "succeeded" for row in members)
                assignment = any(m.get("group_id") == group and m.get("dispatch_intent", {}).get("worker_assignment")
                                 for m in value["messages"])
                value["messages"].append(dict(id=message_id, request_id=first["request_id"].rsplit(":", 1)[0],
                                              group_id=group, task_ids=[r["id"] for r in members], role="assistant",
                                              status="done", provider="dispatcher" if assignment else "max-mode",
                                              content=self.redact(group_result_receipt(members, "Worker assignments" if assignment else "Max mode")),
                                              created_at=time.time(), task_status="succeeded" if success else "partial",
                                              subtasks=[{k: r.get(k) for k in ("id", "title", "worker", "status", "claimed_at", "started_at", "execution_started_at", "finished_at", "result_sha256")} for r in members]))
                for message in value["messages"]:
                    if message.get("group_id") == group and message.get("action_card"):
                        message["action_card"]["state"] = "done" if success else "blocked"
                self.save(value)
                self.conversations[identifier] = value
            for row in members:
                import alignment_events
                try:
                    alignment_events.record_task_result(self.root, row, self.redact)
                except OSError:
                    continue
                task_queue.delivered(self.root, row["id"], message_id)

    def migrate_legacy_tasks(self):
        """Recover accepted pre-dispatch jobs using their saved chat queue receipts."""
        with self.lock:
            if self.closing.is_set():
                return
            self._migrate_legacy_tasks()

    def _migrate_legacy_tasks(self):
        for current in list(self.conversations.values()):
            value = copy.deepcopy(current)
            changed = False
            for message in value["messages"]:
                card = message.get("action_card") or {}
                filename = card.get("queue_id") or ""
                if card.get("state") != "queued" or not filename.endswith(".md") or Path(filename).name != filename or message.get("task_id"):
                    continue
                path = self.root / "next-prompts" / filename
                if not path.is_file():
                    continue
                match = re.search(r"##\s*Task\s*\n+(.+?)(?:\n##|\Z)", path.read_text(), re.S | re.I)
                if not match:
                    continue
                prompt = match.group(1).strip()
                row = task_queue.enqueue(self.root, value["id"], message["request_id"], prompt,
                                         kind=task_kind(prompt), source_file=filename)
                message["task_id"] = row["id"]
                card["task_id"] = row["id"]
                changed = True
            if changed:
                self.save(value)
                self.conversations[value["id"]] = value

"""Chat task submission and durable result delivery, independent of chat models."""
from __future__ import annotations

import copy
import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "state"))
import task_queue
import max_mode

POLITE = r"(?:(?:please|bob)[,:]?\s+|(?:can|could|would|will) you\s+|i (?:want|need) (?:you )?to\s+|let['’]s\s+)*"
WORK = re.compile(
    r"^" + POLITE +
    r"(?:review|analy[sz]e|audit|research|investigate|inspect|check|compare|summari[sz]e|calculate|"
    r"read|open|save|append|write|draft|create|build|implement|fix|repair|debug|test|trace|update|refactor|add|remove|"
    r"diagnose|figure out|find out|look into|work on|improve|make)\b.*", re.I | re.S)
PREAMBLE = re.compile(r"^(?:(?:ok(?:ay)?|yes|yeah|sure|great|thanks)[,.!]?\s+)+", re.I)
ROUTED = re.compile(r"^" + POLITE + r"(?:have|get|ask|use|assign(?:\s+to)?|delegate(?:\s+to)?)\s+"
                    r"(codex|claude|cursor-agent|cursor|gemini|minimax|mini|grok)\b\s*(?:to\b|[:,])?\s*(.*)$", re.I | re.S)
PREFIX = re.compile(r"^(?:worker\s*[:=]\s*)?(codex|claude|cursor-agent|cursor|gemini|minimax|mini|grok)\s*:\s*(.+)$", re.I | re.S)
CODING = re.compile(r"\b(?:fix|repair|implement|refactor|debug|build|run|execute|install|edit|change|modify)\b|"
                    r"\b(?:write|add|create|update|remove)\b.{0,60}\b(?:code|file|test|function|service|script|app|feature)\b", re.I | re.S)
FOLLOW_UP = re.compile(r"^(?:go(?: ahead)?|do it|handle it|yes(?: please)?|let['’]s do it)[.!?]*$", re.I)
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
    if conversation.get("pending_job"):
        prompt = conversation["pending_job"]
        work, worker = parse_work(prompt)
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
    proposal = PROPOSAL.fullmatch(text)
    if not proposal or re.search(r"\bor\b|\n|[.!?]\s", proposal[1], re.I):
        return None, "auto"
    prompt = re.sub(r"^take a look at\b", "review", proposal[1], flags=re.I)
    return parse_work(prompt)


def parse_work(text):
    text = PREAMBLE.sub("", text.strip())
    if CHAT_STYLE.match(text):
        return None, "auto"
    if max_mode.MAX_MODE.search(text):
        return text.strip(), "max"
    lane = re.fullmatch(r"(?:start|run)\s+(?:a\s+)?lane\s+(codex|cursor-agent|cursor|claude|gemini|minimax|grok)\s*:\s*(.+)", text.strip(), re.I | re.S)
    if lane:
        return lane[2].strip(), lane[1].lower()
    routed = ROUTED.match(text.strip()) or PREFIX.match(text.strip())
    if routed:
        return routed.group(2).strip(), routed.group(1).lower()
    if WORK.match(text.strip()):
        return text.strip(), "auto"
    return None, "auto"


def task_receipt(row):
    names = {"codex": "Codex", "claude": "Claude", "cursor": "Cursor", "gemini": "Gemini", "minimax": "MiniMax", "mini": "mini"}
    if row["status"] in task_queue.ACTIVE:
        label = "Started on " + names[row["worker"]]
    else:
        worker = row["requested_worker"]
        label = "Queued" + (" for " + names[worker] if worker != "auto" else "")
    return label + " — job " + row["id"] + "."


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
    # An analysis of code is still analysis; actual edits/execution need a CLI.
    if re.search(r"\bread[- ]only\b", prompt, re.I) and re.search(r"\b(?:review|audit|analysis|inspection)\b", prompt, re.I):
        return "analysis"
    if re.match(r"^(?:please\s+)?(?:review|analy[sz]e|audit|compare|summari[sz]e|research|draft|calculate)\b", prompt, re.I):
        return "analysis"
    return "coding" if CODING.search(prompt) else "analysis"


class TaskDispatch:
    def submit_max_task(self, conversation, description, request_id):
        return self.submit_task(conversation, description, request_id, worker="max")

    def submit_task(self, conversation, description, request_id, worker="auto"):
        from app import hard_rule_refusal
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
        try:
            maximum = worker == "max"
            worker = "auto" if maximum else task_queue.worker_name(worker)
            kind = task_kind(max_mode.MAX_MODE.sub("", description).strip(" :,-\n") if maximum else description)
            if not maximum:
                task_queue.validate_worker(worker, "local" if worker == "mini" else kind)
            refusal = hard_rule_refusal(description)
            if refusal:
                raise ValueError(refusal)
            if self.ledger_root(identifier) != self.root:
                raise ValueError("Worker dispatch is disabled in a drill overlay. Use a normal conversation.")
            if (self.root / "conductor/MAINTENANCE").exists():
                raise ValueError("Scheduling is paused for maintenance; this task was not queued.")
            if maximum:
                goal, subtasks = max_mode.plan(self.root, description, kind)
        except ValueError as exc:
            message.update(status="done", content=str(exc), action_card={"state": "refused", "executable": False})
            self.save(conversation)
            self.conversations[identifier] = conversation
            return self.public(conversation)
        # Save the originating message AND intent before the queue side effect.
        # Startup/reconciliation retries this idempotently after either write fails.
        intent = dict(prompt=description, worker=worker, kind=kind, request_id=request_id)
        if maximum:
            intent.update(goal=goal, subtasks=subtasks)
        message.update(status="done", content="Saving your task for a worker…", dispatch_intent=intent)
        self.save(conversation)
        self.conversations[identifier] = conversation
        self.reconcile_tasks()
        return self.public(self.conversations[identifier])

    def reconcile_tasks(self):
        with self.lock:
            for identifier, current in list(self.conversations.items()):
                value = copy.deepcopy(current)
                changed = False
                for message in value["messages"]:
                    intent = message.get("dispatch_intent")
                    if not intent or message.get("task_id") or message.get("group_id"):
                        continue
                    if intent.get("subtasks"):
                        rows = max_mode.enqueue(self.root, identifier, intent)
                        group = rows[0]["group_id"]
                        message.update(group_id=group, task_ids=[row["id"] for row in rows], status="done", provider="dispatcher",
                                       content="Queued " + str(len(rows)) + " tasks — group " + group + ".",
                                       action_card={"id": message["request_id"], "state": "queued", "executable": False,
                                                    "group_id": group, "queue_id": group, "goal_text": intent["goal"][:160]})
                        changed = True
                        continue
                    row = task_queue.enqueue(self.root, identifier, intent["request_id"], intent["prompt"],
                                             worker=intent["worker"], kind=intent["kind"])
                    message.update(task_id=row["id"], status="done", provider="dispatcher",
                                   content=task_receipt(row),
                                   action_card={"id": message["request_id"], "state": "queued", "executable": False,
                                                "queue_id": row["id"], "task_id": row["id"], "goal_text": row["prompt"][:160]})
                    changed = True
                if changed:
                    self.save(value)
                    self.conversations[identifier] = value
            all_rows = list(task_queue.tasks(self.root).values())
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
                                message.update(content=task_receipt(row))
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
                    content = ("Job `" + row["id"] + "` finished on " + row["worker"] + ":\n\n" + row["result"] if success else
                               "Job `" + row["id"] + "` failed after " + str(row["attempts"]) + " attempts on " + str(row["worker"]) + ": " + row.get("error", "Unknown worker failure"))
                    value["messages"].append(dict(id=message_id, request_id=row["request_id"], task_id=row["id"],
                                                  role="assistant", status="done", provider=row["worker"],
                                                  content=self.redact(content), created_at=time.time(),
                                                  task_status=row["status"], claimed_at=row["claimed_at"],
                                                  started_at=row.get("started_at"), finished_at=row["finished_at"]))
                    for message in value["messages"]:
                        if message.get("task_id") == row["id"] and message.get("action_card"):
                            message["action_card"].update(state="done" if success else "blocked", worker=row["worker"])
                    self.save(value)  # Commit the answer BEFORE acknowledging outbox delivery.
                    self.conversations[identifier] = value
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
                value["messages"].append(dict(id=message_id, request_id=first["request_id"].rsplit(":", 1)[0],
                                              group_id=group, task_ids=[r["id"] for r in members], role="assistant",
                                              status="done", provider="max-mode", content=self.redact(max_mode.merge_text(members)),
                                              created_at=time.time(), task_status="succeeded" if success else "partial",
                                              subtasks=[{k: r.get(k) for k in ("id", "title", "worker", "status", "claimed_at", "started_at", "execution_started_at", "finished_at", "result_sha256")} for r in members]))
                for message in value["messages"]:
                    if message.get("group_id") == group and message.get("action_card"):
                        message["action_card"]["state"] = "done" if success else "blocked"
                self.save(value)
                self.conversations[identifier] = value
            for row in members:
                task_queue.delivered(self.root, row["id"], message_id)

    def migrate_legacy_tasks(self):
        """Recover accepted pre-dispatch jobs using their saved chat queue receipts."""
        with self.lock:
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

"""Dispatch acknowledgements come from this turn's durable journal entries."""
import re


NO_DISPATCH = "I did not start, assign, or queue any work in this turn."
WORKERS = r"(?:Codex|Claude|Cursor|Gemini|MiniMax|the (?:system|dispatcher|workers?)|all (?:LLMs|workers))"
EFFECT = r"(?:start(?:ed|ing)?|assign(?:ed|ing)?|queue(?:d|ing)?|queuing|dispatch(?:ed|ing)?|launch(?:ed|ing)?|schedul(?:e|ed|ing)|delegat(?:e|ed|ing)|add(?:ed|ing)? work|put .{0,40} to work|kick(?:ed|ing)? off)"
CLAIM = re.compile(
    r"\b(?:I|we|Bob|" + WORKERS + r")\b[^.!?\n]{0,90}\b" + EFFECT + r"\b|"
    r"(?:^|[.!?\n]\s*)(?:queued|assigned|started|dispatched|launched|scheduled)\b|"
    r"\b(?:work|jobs?|tasks?|reviews?|audits?|tests?)\b[^.!?\n]{0,80}\b(?:has|have|is|are|was|were|being|been)\b"
    r"[^.!?\n]{0,30}\b" + EFFECT + r"\b|"
    r"\b(?:I['’]ll|I will|we['’]ll|we will|the system (?:will|is))\b[^.!?\n]{0,100}"
    r"\b(?:make sure|ensure|utiliz|prioritiz|keep .{0,35}busy|maximize|adding work)|"
    r"\b" + WORKERS + r"\b.{0,45}\b(?:is|are) (?:now )?(?:working|running|busy|on it)\b|"
    r"\b(?:I['’]ve|I have|we['’]ve|we have) (?:put|got|set)\b[^.!?\n]{0,60}\b(?:working|busy|work|task|job)\b",
    re.I,
)
JOB_ID = re.compile(r"\bwebchat-[a-f0-9]{32}\b")


def claims_dispatch(text):
    # Code examples and quoted user input are not action acknowledgements.
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    prose = re.sub(r"(?:^|(?<=[.!?])\s+)(?:A job|Jobs|A task|Tasks)\b[^.!?]*\b(?:when|if|until)\b[^.!?]*[.!?]?", "", prose, flags=re.I)
    # A conditional offer is not a claim that work was done.
    prose = re.sub(r"(?:^|(?<=[.!?])\s+)I (?:can|could)\b[^\n]*", "", prose, flags=re.I)
    return bool(CLAIM.search(prose) or JOB_ID.search(prose))


def receipt_errors(answer, records, conversation_id, request_id, turn_started_at):
    """Reject invented, old, foreign, uncited, or omitted dispatch receipts."""
    identifiers = answer.get("task_ids") or ([answer["task_id"]] if answer.get("task_id") else [])
    errors = []
    for identifier in identifiers:
        row = records.get(identifier)
        if not row:
            errors.append("job does not exist: " + identifier)
            continue
        expected = request_id + ":" + str(row["group_index"]) if row.get("group_id") else request_id
        if row.get("conversation_id") != conversation_id or row.get("request_id") != expected:
            errors.append("job belongs to another turn: " + identifier)
        if row.get("created_at", 0) < turn_started_at:
            errors.append("job predates this turn: " + identifier)
        if identifier not in answer.get("content", ""):
            errors.append("receipt does not cite job: " + identifier)
    if len(identifiers) != len(set(identifiers)):
        errors.append("duplicate receipt ID")
    if set(JOB_ID.findall(answer.get("content", ""))) - set(identifiers):
        errors.append("reply cites a job outside its dispatch receipts")
    expected_ids = {row["id"] for row in records.values()
                    if row.get("conversation_id") == conversation_id and
                    (row.get("request_id") == request_id or
                     row.get("request_id", "").startswith(request_id + ":"))}
    if expected_ids != set(identifiers):
        errors.append("reply does not account for every job created in this turn")
    return errors


def verify_saved_receipt(root, conversation, message):
    import task_queue
    user = next(m for m in conversation["messages"] if m.get("role") == "user"
                and m.get("request_id") == message["request_id"])
    errors = receipt_errors(message, task_queue.tasks(root), conversation["id"],
                            message["request_id"], user["created_at"])
    if errors:
        raise ValueError("Cannot acknowledge dispatch: " + "; ".join(errors))

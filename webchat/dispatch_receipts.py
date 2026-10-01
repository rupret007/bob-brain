"""Dispatch acknowledgements come from this turn's durable journal entries."""
import re


NO_DISPATCH = "I did not start, assign, or queue any work in this turn."
WORKERS = r"(?:Codex|Claude|Cursor|Gemini|MiniMax|the (?:system|dispatcher|workers?)|all (?:LLMs|workers))"
EFFECT = r"(?:start(?:ed|ing)?|creat(?:e|ed|ing)\b[^.!?\n]{0,60}\b(?:jobs?|tasks?)|assign(?:ed|ing)?|queue(?:d|ing)?|queuing|dispatch(?:ed|ing)?|launch(?:ed|ing)?|schedul(?:e|ed|ing)|delegat(?:e|ed|ing)|add(?:ed|ing)? work|put .{0,40} to work|kick(?:ed|ing)? off)"
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
# In an explanation, generic jobs are examples. Owner references and named
# jobs still make concrete claims; they need the same real receipts as actions.
REFERENCE_TARGET = (r"\b(?:your|our|my|this|that|these|those)\b[^.;!?\n]{0,60}\b(?:jobs?|tasks?|work|council)\b|"
                    r"\bthe\s+(?:(?!(?:a|an|the|is|are|was|were|has|have|means|when|once|if|until|job|task|work|queue|state|queued|running|scheduled|assigned|waiting)\b)[\w'-]+\s+){1,4}(?:job|task)\b")
REFERENCE_EFFECT = re.compile(
    r"(?:^|[.!?\n]\s*)(?:queued|assigned|started|dispatched|launched|scheduled)\b|"
    r"(?:" + REFERENCE_TARGET + r")[^.;!?\n]{0,80}\b" + EFFECT + r"\b|"
    r"\b(?:the|a) (?:job|task) (?:is|was|has|had)\s+(?:(?:just|now|already|been)\s+)*" + EFFECT + r"\b", re.I)
DIRECT_CLAIM = re.compile(
    r"\b(?:I|we|Bob|" + WORKERS + r")\b[^.!?\n]{0,90}\b" + EFFECT + r"\b|"
    r"\b" + WORKERS + r"\b.{0,45}\b(?:is|are) (?:now )?(?:working|running|busy|on it)\b|"
    r"\b(?:I['’]ve|I have|we['’]ve|we have) (?:put|got|set)\b[^.!?\n]{0,60}\b(?:working|busy|work|task|job)\b",
    re.I,
)


def dispatch_prose(text, *, reference=''):
    # Code examples and quoted user input are not action acknowledgements.
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    # Mask only a generic conditional's state predicate, in either order.
    # Never erase its following clauses: they may assert a real owned/named
    # effect even without an explicit actor or job ID.
    predicate = r'(?:a (?:job|task)|jobs|tasks)\s+(?:is|are|has|have)\s+(?:been\s+)?(?:queued|running|started|assigned|scheduled)\b'
    conditional = r'(?:when|if|until|once)'
    prose = re.sub(r'\b' + conditional + r'\s+' + predicate,
                   'the described condition', prose, flags=re.I)
    prose = re.sub(r'(?:^|(?<=[.!?])\s+)' + predicate + r'(?=\s+' + conditional + r'\b)',
                   'The described state', prose, flags=re.I)
    # A conditional offer is not a claim that work was done.
    prose = re.sub(r"(?:^|(?<=[.!?])\s+)I (?:can|could)\b(?:(?!\b(?:and|but)\s+(?:I|we|Bob)\b(?![’\x27]ll|\s+(?:will|can|could)\b))[^.;!?\n])*[.!?]?", "", prose, flags=re.I)
    prose = re.sub(r"\bI (?:can(?:not|['’]t)|could(?: not|n['’]t)|did(?: not|n['’]t)|have(?: not|n['’]t))\b"
                   r"(?:(?!\b(?:and|but)\s+(?:I|we|Bob)\b)[^.;!?\n])*", "", prose, flags=re.I)
    # Replace only the explicitly excluded verb. Separate positive claims
    # remain visible to the guard, including after a semicolon or conjunction.
    prose = re.sub(r'\bwithout\s+' + EFFECT + r'\b', 'without performing an action', prose, flags=re.I)
    if reference:
        # In a definition, generic subjects describe the term, not a live job.
        # Preserve owner/named-job, actor and deictic claims for the guard.
        def definition_subjects(match):
            part = match[0]
            if (DIRECT_CLAIM.search(part) or JOB_ID.search(part) or re.search(REFERENCE_TARGET, part, re.I)
                    or re.search(r'\b(?:now|just|already|currently|today|here|this|that)\b', part, re.I)):
                return part
            return re.sub(r'\b(?:the|a) (?:job|task)\b', 'the described state', part, flags=re.I)
        prose = re.sub(r'(?:^|(?<=[.;!?])\s+)(?:queued|running|assigned|scheduled)\s+means\b[^.;!?\n]*',
                       definition_subjects, prose, flags=re.I)
        # Exempt only a definition's subject, never the rest of its sentence.
        # "Queued means accepted; I started it" must still fail the guard.
        prose = re.sub(r'(?im)(^|[.!?]\s+)(queued)(?=\s+(?:means|does not prove|is a state)\b)',
                       r'\1The queue state', prose)
        # A supplied generic state may be discussed verbatim. No actor, owner,
        # job ID, or named task can acquire an action receipt through this path.
        state = r'\b(?:the|a) (?:job|task) is (?:queued|running|started|assigned)\b'
        supplied = {m[0].casefold() for m in re.finditer(state, reference, re.I)}
        prose = re.sub(state, lambda m: 'the supplied state' if m[0].casefold() in supplied else m[0],
                       prose, flags=re.I)
    return prose


def claims_dispatch(text, *, reference=''):
    # Direct actors and concrete IDs never receive a reference exemption.
    original = dispatch_prose(text)
    # Do not use the passive proximity heuristic for a conceptual answer: a
    # definition can describe assignment without asserting a particular job.
    claim = REFERENCE_EFFECT if reference else CLAIM
    return bool(DIRECT_CLAIM.search(original) or JOB_ID.search(original)
                or claim.search(dispatch_prose(text, reference=reference)))


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

"""Explicit project report assignments on the existing durable task path."""
import hashlib
import json
from pathlib import Path
import re
import time

import project_context
import report_contract
import report_artifacts
import task_queue
from answer_intent import instructions

ACTION = re.compile(r'^(?:please\s+)?(?:(?:can|could|would) you\s+(?:please\s+)?)?'
                    r'(?:(?:have|ask|use)\s+(codex|claude|cursor|gemini|minimax|grok)\s+(?:to\s+)?)?'
                    r'(?:create|prepare|produce|write|save|investigate|inspect|review|turn)\b', re.I)
REPORT = re.compile(r'\b(?:readiness report|project report|next[- ]actions brief|prioriti[sz]ed (?:brief|next actions))\b', re.I)
NO_ACTION = re.compile(r"\b(?:don't|do not|don’t|only explain|just explain|later|eventually|not yet|if|unless|once|after I)\b", re.I)
SOURCE_PATHS = ('docs/PERSISTENT-CONTEXT.md', 'webchat/project_context.py', 'webchat/task_dispatch.py',
                'services/subscription_report.py', 'state/task_queue.py', 'release/README.md')


def recognizes(text):
    value = instructions(text).strip()
    return bool(ACTION.match(value) and REPORT.search(value) and not NO_ACTION.search(value))


def verified_report(root, identifier):
    row = task_queue.tasks(root).get(identifier)
    if not row or row['status'] != 'succeeded' or not row.get('report_contract'):
        raise ValueError('That report has no completed bounded assignment to inspect.')
    contract = row['report_contract']
    raw = report_artifacts.read(root, contract['output_relative'])
    answer = row.get('result', '')
    digest = hashlib.sha256(answer.encode()).hexdigest()
    if (raw != (answer + '\n').encode() or digest != row.get('result_sha256') or
            row.get('acceptance', {}).get('accepted') is not True or
            row.get('acceptance', {}).get('result_sha256') != digest or
            row['acceptance'].get('contract_sha256') != contract['contract_sha256']):
        raise ValueError('The saved report failed its integrity check; no new assignment was created.')
    return row, raw.decode()


def collect(chat, snapshot, text, *, source_root=None):
    """Selection is server owned, bounded and explicitly labelled as a snapshot."""
    source_root = Path(source_root or Path(__file__).resolve().parents[1])
    sources, manifest, coverage = [], [], []
    def add(path, body, kind):
        body = chat.redact(body)
        raw = body.encode()
        sources.append(dict(path=path, text=body))
        manifest.append(dict(path=path, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), source_type=kind))
    add('snapshot/project-context.json', report_contract.canonical(snapshot), 'owner_context')
    source_id = re.search(r'\bwebchat-[a-f0-9]{32}\b', text)
    wants_brief = bool(re.search(r'\b(?:brief|next[- ]actions)\b', text, re.I))
    if wants_brief:
        if source_id:
            identifier = source_id[0]
        else:
            rows = [r for r in task_queue.tasks(chat.root).values() if r['status'] == 'succeeded'
                    and (r.get('report_contract') or {}).get('goal_id') == snapshot['goal_id']]
            latest = max(rows, key=lambda r:r.get('finished_at', 0), default=None)
            if latest is None:
                raise ValueError('A completed project report is needed for the next-actions brief. Create the readiness report first.')
            identifier = latest['id']
        row, body = verified_report(chat.root, identifier)
        if row['report_contract']['goal_id'] != snapshot['goal_id']:
            raise ValueError('The report belongs to a different project.')
        add(row['report_contract']['output_relative'], body, 'verified_report')
        coverage.append(dict(source_job_id=row['id'], source_contract=row['report_contract']['contract_sha256'],
                             source_goal_revision=row['report_contract']['goal_revision'],
                             current_goal_revision=snapshot['revision'],
                             use='Historical report; use latest owner context where it conflicts'))
    else:
        if snapshot['project_id'] != 'web-bob':
            raise ValueError('The bounded source collector currently supports Web Bob. Other projects need an explicitly reviewed evidence collector.')
        for path in SOURCE_PATHS:
            try:
                raw = report_artifacts.read(source_root, path, 200000)
            except FileNotFoundError:
                coverage.append(dict(path=path, available=False))
                continue
            clipped = raw[:12500]
            if len(raw) > len(clipped):
                clipped = clipped.rsplit(b'\n', 1)[0]
            body = clipped.decode('utf-8')
            add(path, body, 'code')
            coverage.append(dict(path=path, complete=len(clipped) == len(raw),
                                 delivered_lines=body.count('\n') + 1, source_bytes=len(raw),
                                 full_source_sha256=hashlib.sha256(raw).hexdigest()))
    observed = dict(observed_at=time.time(), code_evidence_root=str(source_root), coverage=coverage,
                    limits='Static bounded source and saved observations; no tests, endpoint probes or messages were run.')
    pins = {}
    for name in ('webchat-code-root', 'web-dispatch-code-root'):
        try:
            pins[name] = report_artifacts.read(chat.root, 'conductor/state/' + name, 4096).decode().strip()
        except (OSError, ValueError):
            pins[name] = None
    observed['saved_pins'] = pins
    observed['tasks'] = [{k:r.get(k) for k in ('id', 'worker', 'status', 'finished_at', 'result_sha256', 'report_checkpoint')}
                         for r in task_queue.tasks(chat.root).values()
                         if (r.get('report_contract') or {}).get('goal_id') == snapshot['goal_id']][-12:]
    add('snapshot/evidence-coverage.json', report_contract.canonical(observed), 'runtime_observation')
    if sum(m['bytes'] for m in manifest) > report_contract.MAX_INPUT_BYTES:
        raise ValueError('The selected report evidence exceeds the context limit; choose a smaller scope.')
    return sources, manifest


def handle(chat, conversation, text, request_id):
    value = instructions(text).strip()
    match = ACTION.match(value)
    if not match or not REPORT.search(value):
        return None
    if NO_ACTION.search(value):
        return chat.intent_reply(conversation, 'That report request is conditional or deferred. '
                               'I have not started it. The bounded route can use saved project context and evidence when you authorize it now.')
    worker = (match[1] or 'claude').lower()
    # Capability is explicit; a missing adapter cannot widen to a coding worker.
    if worker != 'claude':
        return chat.intent_reply(conversation, 'This bounded report route supports Claude’s subscription login. '
                               'The requested worker has no qualified evidence-only adapter here; no job was created.')
    if not re.search(r'\bread[- ]only\b', value, re.I):
        return chat.intent_reply(conversation, 'I can prepare that as a saved read-only project report. '
                               'Say “create a read-only Web Bob readiness report” to authorize that bounded investigation.')
    try:
        if chat.ledger_root(conversation['id']) != chat.root:
            raise ValueError('Report dispatch is unavailable in a drill conversation.')
        snapshot = project_context.projection(chat.root, conversation, value)
        if not snapshot or not snapshot.get('available') or snapshot.get('omitted'):
            raise ValueError('Save the project priority first so the report has a clear objective. '
                             'For example: “For the Web Bob project, remember the priority: reliable daily assistance.”')
        sources, manifest = collect(chat, snapshot, value)
        contract = report_contract.build(conversation_id=conversation['id'], request_id=request_id,
            prompt=value, worker=worker, goal_id=snapshot['goal_id'], goal_revision=snapshot['revision'],
            input_manifest=manifest, expected_deliverable='A source-backed report answering the assigned question, '
            'with evidence, prioritized actions, tradeoffs, pending decisions and honest limits. Apply the latest owner correction.')
    except (OSError, ValueError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'The assigned evidence could not be read or saved safely.'
        return chat.intent_reply(conversation, message)
    # submit_task saves the exact source snapshot with the original intent;
    # reconciliation publishes those bytes before the queue append. A restart
    # never recollects a changing snapshot under the same assignment identity.
    return chat.submit_task(conversation, value, request_id, worker=worker, report_contract=contract,
                            report_inputs=sources, attempt_limit=1)

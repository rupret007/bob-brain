"""Versioned, immutable authority for one bounded evidence-to-report task.

This is an extension of task_queue's identity and lease, not a second executor.
The caller is the authenticated product path; imported handoffs cannot enqueue.
"""
import hashlib
import json
import re
import uuid
from pathlib import PurePosixPath

VERSION = 1
WORKERS = ('codex', 'claude')
EFFECTS = ['read_assigned_evidence', 'return_report']
MAX_INPUT_BYTES = 120000
ID = re.compile(r'^[a-z0-9][a-z0-9-]{0,79}$')
SHA = re.compile(r'^[a-f0-9]{64}$')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def task_id(conversation_id, request_id):
    return 'webchat-' + uuid.uuid5(uuid.NAMESPACE_URL, 'webbob:' + conversation_id + ':' + request_id).hex


def relative(value):
    return (isinstance(value, str) and 0 < len(value) <= 240 and not re.search(r'[\x00-\x1f\\]', value)
            and not PurePosixPath(value).is_absolute() and
            all(part not in ('', '.', '..') for part in value.split('/')))


def validate(value, *, conversation_id, request_id, prompt, worker, attempt_limit):
    """Reject widening, stale identity and unsupported routes before queue append."""
    try:
        if not isinstance(value, dict):
            raise ValueError()
        required = {'version', 'task_id', 'goal_id', 'goal_revision', 'assignment_revision',
                    'owner', 'scope', 'allowed_effects', 'input_manifest', 'expected_deliverable',
                    'attempt_limit', 'timeout_seconds', 'permitted_workers', 'authorization_request_id',
                    'output_relative', 'contract_sha256'}
        if 'generation_binding' in value:
            required.add('generation_binding')
            binding = value['generation_binding']
            if binding is not None:
                import generation_budget
                if (not isinstance(binding,dict) or set(binding) != {'root','id','purpose','request_id','actor_sha256','input_sha256'} or
                        binding['request_id'] != request_id or binding['purpose'] != 'product' or
                        not isinstance(binding['root'],str) or not binding['root'].startswith('/') or
                        not generation_budget.ID.fullmatch(binding['id']) or
                        binding['input_sha256'] != hashlib.sha256(prompt.encode()).hexdigest() or
                        not SHA.fullmatch(binding['actor_sha256'])):
                    raise ValueError()
        if set(value) != required:
            raise ValueError()
        body = {k:v for k,v in value.items() if k != 'contract_sha256'}
        if (type(value['version']) is not int or value['version'] != VERSION or value['task_id'] != task_id(conversation_id, request_id) or
                value['contract_sha256'] != digest(body) or not ID.fullmatch(value['goal_id']) or
                type(value['goal_revision']) is not int or value['goal_revision'] < 0 or
                type(value['assignment_revision']) is not int or value['assignment_revision'] != 1 or
                value['owner'] != worker or worker not in WORKERS or
                value['scope'] != prompt or not 1 <= len(prompt) <= 6000 or
                value['allowed_effects'] != EFFECTS or value['permitted_workers'] != [worker] or
                value['authorization_request_id'] != request_id or type(attempt_limit) is not int or
                attempt_limit != 1 or type(value['attempt_limit']) is not int or value['attempt_limit'] != 1 or
                type(value['timeout_seconds']) is not int or not 1 <= value['timeout_seconds'] <= 900 or
                not isinstance(value['expected_deliverable'], str) or not 1 <= len(value['expected_deliverable']) <= 1000):
            raise ValueError()
        expected_output = 'conductor/state/project-reports/' + value['goal_id'] + '/' + value['task_id'] + '.md'
        if value['output_relative'] != expected_output:
            raise ValueError()
        manifest = value['input_manifest']
        if (not isinstance(manifest, list) or not 1 <= len(manifest) <= 40 or
                len({m['path'] for m in manifest}) != len(manifest)):
            raise ValueError()
        size = 0
        for item in manifest:
            if (not isinstance(item, dict) or set(item) != {'path','sha256','bytes','source_type'} or
                    not relative(item['path']) or not SHA.fullmatch(item['sha256']) or
                    type(item['bytes']) is not int or not 0 < item['bytes'] <= MAX_INPUT_BYTES or
                    item['source_type'] not in ('code', 'verified_report', 'owner_context', 'runtime_observation')):
                raise ValueError()
            size += item['bytes']
        if size > MAX_INPUT_BYTES:
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('Invalid bounded report contract; no work was admitted.') from None
    return json.loads(canonical(value))


def build(*, conversation_id, request_id, prompt, worker, goal_id, goal_revision,
          input_manifest, expected_deliverable, timeout_seconds=900, generation_binding=None):
    identifier = task_id(conversation_id, request_id)
    value = dict(version=VERSION, task_id=identifier, goal_id=goal_id, goal_revision=goal_revision,
                 assignment_revision=1, owner=worker, scope=prompt, allowed_effects=list(EFFECTS),
                 input_manifest=input_manifest, expected_deliverable=expected_deliverable,
                 attempt_limit=1, timeout_seconds=timeout_seconds, permitted_workers=[worker],
                 authorization_request_id=request_id,
                 output_relative='conductor/state/project-reports/' + goal_id + '/' + identifier + '.md')
    value['generation_binding'] = generation_binding
    value['contract_sha256'] = digest(value)
    return validate(value, conversation_id=conversation_id, request_id=request_id, prompt=prompt,
                    worker=worker, attempt_limit=1)

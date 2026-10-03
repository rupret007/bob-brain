"""An explicit, hash-bound owner deferral never becomes an unrestricted PASS."""
import hashlib
import json
import os
from pathlib import Path

DEFERRED = ['voice-browser', 'live-voice-probes']
VOICE = dict(status='NOT RUN', reason='Owner deferred live voice qualification')


def _read(ref):
    if not isinstance(ref,dict) or set(ref)!={'path','sha256'}:
        raise RuntimeError('Qualification scope reference is invalid')
    path=Path(ref['path'])
    if not path.is_absolute() or path.is_symlink() or path.stat().st_size>32000:
        raise RuntimeError('Qualification scope evidence is unavailable')
    value=path.read_bytes()
    if hashlib.sha256(value).hexdigest()!=ref['sha256']:
        raise RuntimeError('Qualification scope evidence changed')
    return json.loads(value)


def validate(ref):
    value=_read(ref)
    if value.get('schema')!=1 or value.get('scope_name')!='nonvoice' or value.get('deferred_checks')!=DEFERRED:
        raise RuntimeError('Only the explicitly admitted live voice deferral is supported')
    admission=_read(value['admission'])
    steer=_read(value['owner_steer'])
    if (admission.get('id')!=value['continuation_id'] or admission.get('adopted') is not True
            or not steer.get('authority_source') or steer.get('limits_unchanged') is not True
            or steer.get('clock_unchanged') is not True):
        raise RuntimeError('Qualification scope lacks its owner/admission evidence')
    return ref


def selected():
    text=os.environ.get('BOB_QUALIFICATION_SCOPE')
    return validate(json.loads(text)) if text else None


def outcome(passed, scope):
    if scope is None:
        return dict(all_pass=bool(passed))
    return dict(all_pass=False, scope_passed=bool(passed), qualification_scope=scope,
                live_voice=dict(VOICE))


def passed(record, scope=None):
    if record.get('rolled_back') or record.get('failure') or record.get('rollback_error'):
        return False
    if scope is None:
        return record.get('all_pass') is True and not record.get('qualification_scope')
    return (record.get('all_pass') is False and record.get('scope_passed') is True
            and record.get('qualification_scope')==scope and record.get('live_voice')==VOICE)


def historical_passed(record):
    scope=record.get('qualification_scope')
    if scope:validate(scope)
    return passed(record,scope)

"""Durable, operator-admitted generation envelopes shared across data roots.

The authenticated product may select an existing envelope, never create or widen
one. Every transport attempt reserves first. An interrupted/unknown call keeps
its reservation. Native invocations are counted separately from model HTTP.
"""
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid

ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$')
PROVIDERS = ('gemini', 'minimax', 'codex', 'cursor', 'claude')


class AdmissionDenied(RuntimeError):
    pass


def atomic(path, value):
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, sort_keys=True, allow_nan=False)
            out.write('\n'); out.flush(); os.fsync(out.fileno())
        os.replace(name, path)
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def folder(root):
    base = Path(root).resolve()
    path = base / 'conductor/state/generation-budgets'
    if not path.is_dir() or path.resolve() != path:
        raise AdmissionDenied('Generation budget is unavailable; no call was admitted.')
    return path


@contextlib.contextmanager
def locked(root, identifier):
    if not isinstance(identifier, str) or not ID.fullmatch(identifier):
        raise AdmissionDenied('A valid generation budget is required.')
    directory = folder(root)
    path = directory / (identifier + '.json')
    lockpath = directory / (identifier + '.lock')
    if path.is_symlink() or lockpath.is_symlink():
        raise AdmissionDenied('Generation budget identity is invalid.')
    fd = os.open(str(lockpath), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            if path.stat().st_size > 4_000_000:
                raise ValueError()
            data = json.loads(path.read_text())
            if data['schema'] != 1 or data['id'] != identifier or not isinstance(data['calls'], dict):
                raise ValueError()
            limits = data['limits']
            for key in ('api_usd', 'direct_attempts', 'native_invocations', 'reserve_usd', 'reserve_attempts'):
                if type(limits[key]) not in (int, float) or not math.isfinite(limits[key]) or limits[key] < 0:
                    raise ValueError()
            for key in ('total_http_attempts', 'request_http_attempts'):
                if key in limits and (type(limits[key]) is not int or limits[key] < 0):
                    raise ValueError()
            if (not data['providers'] or any(p not in PROVIDERS for p in data['providers']) or
                    data['phase'] not in ('tuning', 'qualification', 'product') or
                    type(data['deadline']) not in (int, float) or not math.isfinite(data['deadline'])):
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            raise AdmissionDenied('Generation budget could not be verified; no call was admitted.') from None
        yield path, data


def totals(data):
    calls = list(data['calls'].values())
    return dict(known_api_usd=sum(c['cost_usd'] for c in calls if c['kind'] == 'http' and c['cost_usd'] is not None),
                reserved_api_usd=sum(c['reserved_usd'] for c in calls if c['kind'] == 'http' and c['cost_usd'] is None),
                direct_attempts=sum(c['kind'] == 'http' and c['purpose'] != 'controller' for c in calls),
                controller_attempts=sum(c['kind'] == 'http' and c['purpose'] == 'controller' for c in calls),
                http_attempts=sum(c['kind'] == 'http' for c in calls),
                native_invocations=sum(c['kind'] == 'native' for c in calls))


def selection(root, identifier):
    with locked(root, identifier) as (_, data):
        if data.get('status') != 'active' or time.time() >= data['deadline']:
            raise AdmissionDenied('This generation budget is stopped or expired.')
        return dict(id=identifier, providers=list(data['providers']), deadline=data['deadline'],
                    chat_providers=list(data.get('chat_providers',data['providers'])),phase=data['phase'], totals=totals(data))


def environment(root, identifier, *, context, base=None):
    env = dict(os.environ if base is None else base)
    selection(root, identifier)
    env.update(BOB_GENERATION_BUDGET=identifier, BOB_GENERATION_BUDGET_ROOT=str(Path(root).resolve()),
               BOB_REQUIRE_GENERATION_BUDGET='1', BOB_GENERATION_CONTEXT=str(context)[:240])
    return env


def attribution(env=None):
    env = os.environ if env is None else env
    identifier = env.get('BOB_GENERATION_BUDGET')
    if not identifier:
        if env.get('BOB_REQUIRE_GENERATION_BUDGET') == '1':
            raise AdmissionDenied('Required goal attribution is missing; no call was admitted.')
        root=env.get('BOB_ROOT')
        policy=read_policy(root) if root else None
        if policy:
            return dict(root=policy['accounting_root'],id=policy['budget_id'],purpose='product',
                        context='normal-provider-boundary',controller_attempt=None,task_id=None)
        return None
    root = env.get('BOB_GENERATION_BUDGET_ROOT')
    if not root or not Path(root).is_absolute():
        raise AdmissionDenied('The shared generation budget root is missing.')
    purpose = env.get('BOB_GENERATION_PURPOSE', 'direct')
    if purpose not in ('direct', 'controller', 'product'):
        raise AdmissionDenied('Invalid generation purpose.')
    controller = env.get('BOB_GENERATION_CONTROLLER_ATTEMPT')
    if purpose == 'controller' and (not controller or not ID.fullmatch(controller)):
        raise AdmissionDenied('Controller generation requires an admitted controller attempt.')
    return dict(root=root, id=identifier, purpose=purpose, context=env.get('BOB_GENERATION_CONTEXT', '')[:240],
                controller_attempt=controller, task_id=env.get('BOB_GENERATION_TASK_ID'),
                request_key=env.get('BOB_GENERATION_REQUEST_KEY'), stage_id=env.get('BOB_GENERATION_STAGE'))


def read_policy(root):
    path=Path(root)/'conductor/state/generation-policy.json'
    if not path.exists() and not path.is_symlink():return None
    try:
        if path.is_symlink() or path.stat().st_size>4096:raise ValueError()
        policy=json.loads(path.read_text())
        if (set(policy)!={'budget_id','accounting_root','purpose'} or policy['purpose']!='product' or
                not Path(policy['accounting_root']).is_absolute() or not ID.fullmatch(policy['budget_id'])):raise ValueError()
        return policy
    except (OSError,ValueError,KeyError,TypeError):
        raise AdmissionDenied('The server generation policy is invalid.') from None


def binding(root, request_id, actor, text, *, env=None, require_active=True):
    """Only trusted process config selects the ledger; request text never does."""
    env = os.environ if env is None else env
    ref = attribution(env)
    if ref is None:
        policy=read_policy(root)
        if policy:ref=dict(root=policy['accounting_root'],id=policy['budget_id'],purpose='product')
    if ref is None:
        return None
    if require_active:selection(ref['root'], ref['id'])
    with locked(ref['root'],ref['id']) as (_,data):
        stage = data.get('active_stage') if data.get('stage_required') else None
    result=dict(root=ref['root'], id=ref['id'], purpose='product', request_id=request_id,
                actor_sha256=hashlib.sha256(str(actor or 'local-operator').encode()).hexdigest(),
                input_sha256=hashlib.sha256(text.encode()).hexdigest())
    if stage:result['stage_id']=stage
    return result


def bound_environment(ref, base):
    if ref is None:
        return dict(base)
    env = environment(ref['root'], ref['id'], context=ref['request_id'], base=base)
    env['BOB_GENERATION_PURPOSE'] = ref['purpose']
    if ref.get('stage_id'):
        env['BOB_GENERATION_STAGE'] = ref['stage_id']
    else:
        env.pop('BOB_GENERATION_STAGE',None)
    env['BOB_GENERATION_REQUEST_KEY'] = hashlib.sha256(json.dumps(
        [ref['request_id'], ref['actor_sha256'], ref['input_sha256']],
        separators=(',', ':')).encode()).hexdigest()
    request_available(ref, env=env)
    return env


def request_available(ref, *, env=None):
    """A saved owner request cannot acquire fresh transport retries on reload."""
    if ref is None:
        return
    with locked(ref['root'], ref['id']) as (_, data):
        if data.get('status')!='active' or time.time()>=data['deadline']:
            raise AdmissionDenied('This saved request’s generation budget is stopped or expired.')
        request=attribution(env) if env is not None else dict(
            context=ref['request_id'],
            stage_id=ref.get('stage_id'),
            request_key=hashlib.sha256(json.dumps(
                [ref['request_id'], ref['actor_sha256'], ref['input_sha256']],
                separators=(',', ':')).encode()).hexdigest())
        active_stage(data,request)
        _request_available(data,request)


def _request_available(data, ref):
    limit = data['limits'].get('request_http_attempts', 3 if 'total_http_attempts' in data['limits'] else None)
    if limit is None or not ref.get('request_key'):
        return
    used = sum(c['kind']=='http' and (c.get('request_key')==ref['request_key'] or
               not c.get('request_key') and c.get('context')==ref.get('context'))
               for c in data['calls'].values())
    if used >= limit:
        raise AdmissionDenied('This saved request has used its transport attempts; automatic retry is stopped.')


def active_stage(data, ref, source=None):
    if not data.get('stage_required'):
        return None
    identifier=ref.get('stage_id')
    stage=data.get('stages',{}).get(identifier,{})
    if (not identifier or data.get('active_stage')!=identifier or stage.get('status')!='active'
            or time.time()>=stage.get('deadline',0) or source and stage.get('source_sha')!=source):
        raise AdmissionDenied('This request is not bound to the current admitted validation stage.')
    limit=stage.get('max_http_attempts')
    if type(limit) is not int or limit<0:
        raise AdmissionDenied('The validation stage has no verified transport ceiling.')
    return stage


def transport_allowed(root, name, *, env=None):
    """Server configuration can exclude a transport before any credential I/O."""
    ref=attribution(dict(os.environ if env is None else env, BOB_ROOT=str(root)))
    if ref:
        selection(ref['root'],ref['id'])
        with locked(ref['root'],ref['id']) as (_,data):
            if name in data.get('excluded_transports',[]):
                raise AdmissionDenied('This transport is deferred in the current validation scope.')


def reserve(provider, bound=0, *, kind='http', call_id=None, env=None):
    ref = attribution(env)
    if ref is None:
        return None
    if kind not in ('http', 'native') or provider not in PROVIDERS or not math.isfinite(bound) or bound < 0:
        raise AdmissionDenied('Invalid generation reservation.')
    with locked(ref['root'], ref['id']) as (path, data):
        if data.get('status') != 'active' or time.time() >= data['deadline'] or provider not in data['providers']:
            raise AdmissionDenied('This provider is not admitted by the active generation budget.')
        source=(os.environ if env is None else env).get('BOB_GENERATION_SOURCE_SHA') or source_identity()
        if data.get('allowed_source_shas') and source not in data['allowed_source_shas']:
            raise AdmissionDenied('This source has not been admitted to the generation budget.')
        used, limits = totals(data), data['limits']
        stage=active_stage(data,ref,source)
        if stage and kind=='http' and sum(c['kind']=='http' and c.get('stage_id')==ref['stage_id']
                                         for c in data['calls'].values())>=stage['max_http_attempts']:
            raise AdmissionDenied('This validation stage has used its admitted transport attempts.')
        if kind == 'http':
            _request_available(data, ref)
        if ref['purpose'] == 'controller':
            controller = data.get('controller_attempts',{}).get(ref['controller_attempt'],{})
            if controller.get('status') != 'active' or time.time() >= controller.get('deadline',0):
                raise AdmissionDenied('That controller attempt is not actively admitted.')
        if ref.get('task_id'):
            jobs = [c for c in data['calls'].values() if c.get('task_id')]
            if (kind != 'native' or any(c['task_id']==ref['task_id'] for c in jobs) or
                    len(jobs) >= limits.get('product_jobs', 0)):
                raise AdmissionDenied('This product job does not fit the one-attempt job allowance.')
        tuning = data['phase'] == 'tuning'
        dollars = limits['api_usd'] - (limits['reserve_usd'] if tuning else 0)
        attempts = limits.get('total_http_attempts', limits['direct_attempts']) - (limits['reserve_attempts'] if tuning else 0)
        # Legacy ledgers retain their original interpretation. A total ceiling
        # admits no controller exemption and counts historical calls unchanged.
        counted = used['http_attempts'] if 'total_http_attempts' in limits else used['direct_attempts']
        exempt = 'total_http_attempts' not in limits and ref['purpose'] == 'controller'
        if kind == 'http' and (used['known_api_usd'] + used['reserved_api_usd'] + bound > dollars + 1e-12 or
                not exempt and counted >= attempts):
            raise AdmissionDenied('The next request does not fit this goal\'s remaining API allowance.')
        if kind == 'native' and used['native_invocations'] >= limits['native_invocations']:
            raise AdmissionDenied('This goal\'s native invocation allowance is exhausted.')
        identifier = call_id or uuid.uuid4().hex
        if identifier in data['calls']:
            raise AdmissionDenied('That generation attempt was already admitted; replay cannot execute it again.')
        data['calls'][identifier] = dict(kind=kind, provider=provider, purpose=ref['purpose'],
            context=ref['context'], reserved_usd=bound, cost_usd=None, admitted_at=time.time(),
            source_sha=source,
            phase=data['phase'], status='reserved', controller_attempt=ref.get('controller_attempt'), task_id=ref.get('task_id'),
            request_key=ref.get('request_key'),
            stage_id=ref.get('stage_id'),
            native_internal_calls_known=False if kind == 'native' else None)
        atomic(path, data)
    return dict(root=ref['root'], id=ref['id'], call_id=identifier)


def source_identity():
    """Direct service calls use their running module's source, never BOB_ROOT."""
    code=Path(__file__).resolve().parents[1]
    try:
        manifest=code/'webbob-build.json'
        if manifest.is_file():value=json.loads(manifest.read_text())['sha']
        else:
            env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
            value=subprocess.check_output(['git','-C',str(code),'rev-parse','HEAD'],env=env,stderr=subprocess.DEVNULL,timeout=5,text=True).strip()
        return value if re.fullmatch('[a-f0-9]{40}',value) else None
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):return None


def settle(ref, cost, *, usage=None, status='response'):
    if not ref:
        return
    if cost is not None and (type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0):
        raise AdmissionDenied('Invalid charge evidence; the reservation remains.')
    with locked(ref['root'], ref['id']) as (path, data):
        row = data['calls'].get(ref['call_id'])
        if row is None:
            raise AdmissionDenied('The admitted generation receipt is missing.')
        # Duplicate settlement never reduces a known charge or releases unknown
        # failure exposure. Retain a provider charge even if it exceeds the bound.
        if cost is not None:
            row['cost_usd'] = max(row.get('cost_usd') or 0, cost)
        row.update(status=status, observed_at=time.time())
        if usage is not None:
            row['usage'] = usage
        atomic(path, data)


def status(root, identifier):
    with locked(root, identifier) as (_, data):
        return dict(id=identifier, status=data['status'], phase=data['phase'], deadline=data['deadline'],
                    limits=data['limits'], providers=data['providers'], **totals(data))


def remaining(ref, *, cleanup_seconds=10):
    if not ref:
        return float('inf')
    with locked(ref['root'],ref['id']) as (_,data):
        deadline=data['deadline']
        row=data['calls'].get(ref.get('call_id'),{})
        stage=active_stage(data,row)
        if stage:deadline=min(deadline,stage['deadline'])
        if row.get('purpose')=='controller':
            controller=data.get('controller_attempts',{}).get(row.get('controller_attempt'),{})
            if controller.get('status')!='active':raise AdmissionDenied('The controller attempt is no longer active.')
            deadline=min(deadline,controller.get('deadline',0))
        seconds = deadline-time.time()-cleanup_seconds
        if data.get('status')!='active' or seconds <= 0:
            raise AdmissionDenied('The goal deadline leaves no transport time; no further generation is allowed.')
        return seconds


def task_block(root, contract=None):
    """An active goal never delegates unaccounted work to a detached executor."""
    try:
        policy=read_policy(root)
        ref=(contract or {}).get('generation_binding')
        if policy and not ref:
            return 'This active generation allowance requires a budget-bound read-only report assignment; the unbound task was not started.'
        if ref:
            selection(ref['root'],ref['id'])
            with locked(ref['root'],ref['id']) as (_,data):active_stage(data,ref)
    except AdmissionDenied as exc:return str(exc)
    return None

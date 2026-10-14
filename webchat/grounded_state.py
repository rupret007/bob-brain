"""Saved/configured/provider/state facts need a server receipt, registry, or record.

Model prose may propose these. It may not assert them unless this turn's context
already contains the backing receipt, route-registry statement, hold request, or
provider record. Diagnostic reasoning never requires releasing a hold.
"""
import hashlib
import re

UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
PROVIDERS = ('Gemini', 'Codex', 'Claude', 'Cursor', 'MiniMax')
PROVIDER_ALT = '|'.join(PROVIDERS)

SAVED_REVISION = re.compile(
    r'\brevision\s+(?P<rev>\d+)\s+of\s+the\s+saved project record\b|'
    r'\bsaved project record(?:\s+loaded with this (?:chat|conversation))?\s+revision\s+(?P<rev2>\d+)\b|'
    r'\bas of revision\s+(?P<rev3>\d+)\b.{0,48}\bsaved project record\b',
    re.I)
LOADED_RECORD = re.compile(
    r'\bsaved project record loaded with this (?:chat|conversation)\b|'
    r'\b(?:loaded|loading|loads)\s+across\s+conversations\b|'
    r'\bcontinuity across conversations is recorded\b',
    re.I)
HOLD_REQUEST = re.compile(
    r'\bhold request ID\b[^.\n]{0,48}(?P<id>' + UUID + r')|'
    r'\b(?:saved|recorded|issued|filed|registered)\b.{0,48}\bhold\b.{0,48}(?P<id2>' + UUID + r')|'
    r'\bhold(?:\s+request)?(?:\s+id)?\s*[:=]?\s*(?P<id3>' + UUID + r')',
    re.I)
CONFIGURED_ROUTE = re.compile(
    r'\b(?:conversation adapters?|scoped executors?)\b.{0,80}\bconfigured\b|'
    r'\bconfigured\b.{0,80}\b(?:conversation adapters?|scoped executors?)\b|'
    r'\bconfigured route registry\b|'
    r'\bconfigured routes? for\b',
    re.I)
LAST_REPLY_PROVIDER = re.compile(
    r"\b(?:Bob's |the )?(?:last|previous|earlier)(?:\s+completed)?\s+"
    r"(?:reply|answer|message)\s+(?:used|was|came from|identified)\s+"
    r"(?P<name>" + PROVIDER_ALT + r")\b|"
    r'\blast completed reply\s+(?:used|was|identified)\s+(?P<name2>' + PROVIDER_ALT + r')\b',
    re.I)
DIAGNOSTICS_REQUIRE_RELEASE = re.compile(
    r'\bdiagnostics?\b.{0,72}\b(?:require|need|must).{0,48}\b(?:releas|lift|clear).{0,24}\bhold\b|'
    r'\b(?:releas|lift|clear).{0,48}\bhold\b.{0,48}\b(?:for|to|before)\b.{0,48}\bdiagnostics?\b|'
    r'\bdiagnostics?\b.{0,24}\brequire(?:s|ing)?\s+(?:hold\s+)?release\b|'
    r'\bhold\b.{0,40}\b(?:must|needs? to|required to)\s+be\s+released\b.{0,48}\bdiagnostics?\b',
    re.I)

NOTE = ('That saved, configured, provider, or hold-state fact is proposed or '
        'unknown without a supporting server receipt, route registry, or provider record.')
HOLD_NOTE = 'Diagnostic reasoning does not require a hold release.'


def conversation_evidence(conversation=None, *, projection=None, source='', prior='',
                          selected=(), trusted_facts=()):
    """Collect backing receipts, registry text, hold IDs, and provider records."""
    texts = [source or '', prior or '']
    texts.extend(trusted_facts or ())
    hold_ids = set()
    providers = []
    revisions = set()
    registry = False
    facts = (projection or {}).get('facts') or {}
    if (facts.get('route_boundaries') or 'route_boundaries' in (selected or ()) or
            'configured route registry' in '\n'.join(texts).lower()):
        registry = True
        if facts.get('route_boundaries'):
            texts.append(facts['route_boundaries'])
    owner = (projection or {}).get('owner_context') or {}
    if owner.get('revision') is not None:
        revisions.add(int(owner['revision']))
        texts.append('saved project record revision ' + str(owner['revision']))
        if owner.get('attribution'):
            texts.append(owner['attribution'])
    route = (projection or {}).get('current_route') or {}
    if route.get('source') == 'last completed reply' and route.get('name'):
        providers.append(route['name'])
    messages = list((conversation or {}).get('messages') or [])
    if messages and messages[-1].get('role') == 'assistant':
        messages = messages[:-1]
    for message in messages:
        if message.get('role') == 'assistant' and message.get('status') == 'done' and message.get('provider'):
            providers.append(str(message['provider']).lower())
        edit = message.get('_project_edit') or {}
        if edit.get('revision') is not None:
            revisions.add(int(edit['revision']))
        content = message.get('content') or ''
        if 'product receipt this turn' in content or 'retrieved this turn' in content:
            texts.append(content)
        decision = message.get('resource_decision') or {}
        if 'route_boundaries' in (decision.get('fact_ids') or ()):
            registry = True
    try:
        from chat_intent import permission_facts
        saved = permission_facts(conversation or {})
        for row in (saved.get('holds') or {}).values():
            if isinstance(row, dict) and row.get('request_id'):
                hold_ids.add(str(row['request_id']).lower())
        last = saved.get('last_permission') or {}
        if last.get('request_id'):
            hold_ids.add(str(last['request_id']).lower())
    except Exception:
        pass
    hay = '\n'.join(str(part) for part in texts if part)
    if re.search(r'\b(?:product receipt this turn|retrieved this turn|saved product (?:record|receipt) retrieved)\b',
                 hay, re.I):
        for match in re.finditer(r'\brevision\s+(\d+)\b', hay, re.I):
            revisions.add(int(match[1]))
    return dict(text=hay, hold_ids=hold_ids, providers=providers,
                revisions=revisions, registry=registry)


def _revision(match):
    for key in ('rev', 'rev2', 'rev3'):
        if match.groupdict().get(key):
            return int(match[key])
    return None


def _hold_id(match):
    for key in ('id', 'id2', 'id3'):
        value = match.groupdict().get(key)
        if value:
            return value.lower()
    return None


def _provider(match):
    for key in ('name', 'name2'):
        value = match.groupdict().get(key)
        if value:
            return value.lower()
    return None


def backed(match, evidence, kind):
    evidence = evidence or {}
    if kind == 'saved_revision':
        rev = _revision(match)
        return rev is not None and rev in set(evidence.get('revisions') or ())
    if kind == 'loaded_record':
        hay = evidence.get('text') or ''
        return bool(re.search(
            r'\b(?:product receipt this turn|retrieved this turn|saved product (?:record|receipt) retrieved|'
            r'saved project record revision\s+\d+)\b', hay, re.I))
    if kind == 'hold_request':
        ident = _hold_id(match)
        hay = (evidence.get('text') or '').lower()
        return bool(ident and (ident in set(evidence.get('hold_ids') or ()) or ident in hay))
    if kind == 'configured_route':
        return bool(evidence.get('registry') or
                    'configured route registry' in (evidence.get('text') or '').lower())
    if kind == 'last_reply_provider':
        name = _provider(match)
        return bool(name and name in {item.lower() for item in evidence.get('providers') or ()})
    return False


def unsourced_matches(clause_text, evidence=None):
    """Yield (match, kind) relative to one clause for unsupported state facts."""
    checks = (
        (SAVED_REVISION, 'saved_revision'),
        (LOADED_RECORD, 'loaded_record'),
        (HOLD_REQUEST, 'hold_request'),
        (CONFIGURED_ROUTE, 'configured_route'),
        (LAST_REPLY_PROVIDER, 'last_reply_provider'),
        (DIAGNOSTICS_REQUIRE_RELEASE, 'diagnostics_require_release'),
    )
    for pattern, kind in checks:
        for match in pattern.finditer(clause_text or ''):
            if kind != 'diagnostics_require_release' and backed(match, evidence, kind):
                continue
            yield match, kind


def unsourced_state_claims(text, evidence=None):
    """Yield (match, kind, statement) for asserted product-state facts lacking backing."""
    from claim_scope import clauses, disposition
    for statement in clauses(text or ''):
        for match, kind in unsourced_matches(statement.text, evidence):
            if disposition(statement, match.start(), match.end(), match[0]):
                continue
            yield match, kind, statement


def state_findings(content, *, source='', trusted_facts=(), evidence=None, artifact=False):
    if artifact or not content:
        return []
    evidence = evidence or conversation_evidence(source=source, trusted_facts=trusted_facts)
    findings = []
    seen = set()
    for match, kind, statement in unsourced_state_claims(content, evidence):
        start, end = statement.start, statement.end
        if (start, end) in seen:
            continue
        seen.add((start, end))
        category = ('diagnostics_require_release' if kind == 'diagnostics_require_release'
                    else 'unsourced_state')
        findings.append(dict(
            start=start, end=end, categories=[category],
            claims=[dict(start=statement.start + match.start(), end=statement.start + match.end(),
                         category=kind, disposition='asserted_without_support')],
            sha256=hashlib.sha256(content[start:end].encode()).hexdigest(),
            reason='state_fact_exceeds_available_support'))
    return findings


def diagnostics_require_release(text):
    return bool(DIAGNOSTICS_REQUIRE_RELEASE.search(text or ''))

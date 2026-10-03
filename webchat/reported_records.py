"""Presentation and subject boundaries for discussing supplied task records.

These helpers provide no execution authority. Real permission/effect checks still
inspect the original text. Headings do not define a vocabulary of permitted facts.
"""
import hashlib
import re

ITEM = re.compile(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)')
SENTENCE = re.compile(r'(?<=[!?])(?=\s)|(?<=[.])(?=\s)(?<!\d\.)')
ENTITY = re.compile(r'\b(?:services?|workers?|reviewers?|daemons?|servers?|processes|process|systems?|apps?|hosts?|agents?|coordinators?|supervisors?)\b|\b[A-Z][A-Za-z]*(?:Worker|Agent|Service|Daemon)\b', re.I)
IDENTIFIER = r'[A-Za-z][\w]*-\d+'
TASK_ID = re.compile(r'\b(?:(?:task|assignment)\s+(?:ID\s+)?|(?:record|card|case|scenario)(?:\s+only)?\s*:\s*(?:task\s+)?)('+IDENTIFIER+r')\b', re.I)


def units(content):
    """Keep list markers with their bodies, including indented continuation."""
    pending = ''
    for line in content.splitlines(keepends=True):
        item = bool(ITEM.match(line))
        if pending:
            if line.strip() and line[0].isspace() and not item:
                pending += line
                continue
            yield pending
            pending = ''
        if item:
            pending = line
        else:
            yield from SENTENCE.split(line)
    if pending:
        yield pending


def presentation(part):
    plain = re.sub(r'[*_`]', '', part)
    plain = re.sub(r'^\s*(?:[-+]\s+|\d+[.)]\s+)?', '', plain)
    label = re.match(r'^([^:\n]{1,128}):\s*', plain)
    return (label[1], plain[label.end():]) if label else ('', plain)


def foreign_label(label, projects, worker_names):
    return bool(projects(label) or ENTITY.search(label) or
                any(re.search(r'\b'+re.escape(name)+r'\b', label, re.I) for name in worker_names))


def foreign_subject(clause, projects, worker_names):
    # Only the grammatical subject changes the referent. Mentioning an actor
    # inside an uncertainty or evidence requirement does not switch the topic.
    subject = re.match(r'^\s*(.{1,96}?)\s+(?:is|are|was|were|remains?|has|have|does|do|did|will|can|may|might|could|must|should)\b', clause, re.I)
    return bool(subject and foreign_label(subject[1], projects, worker_names))


def source_bindings(record):
    excerpts = (record or {}).get('user_excerpts', [])
    # Associated lease/snapshot/artifact identifiers are not task subjects.
    # Follow-up references can reuse an identity established by its task role.
    tasks = {m[1] for excerpt in excerpts for m in TASK_ID.finditer(excerpt.get('content', ''))}
    result = {}
    for excerpt in excerpts:
        text = excerpt.get('content', '')
        binding = dict(message_id=excerpt['message_id'], request_id=excerpt['request_id'],
                       excerpt_sha256=hashlib.sha256(text.encode()).hexdigest(),
                       truncated=excerpt.get('truncated', False))
        for identifier in re.findall(r'\b[A-Za-z][\w]*-\d+\b', text):
            if identifier in tasks:
                result.setdefault(identifier, []).append(binding)
    return result


def receipt(part, *, offset, accepted, reason, subject, bindings):
    return dict(start=offset, end=offset+len(part), sha256=hashlib.sha256(part.encode()).hexdigest(),
                accepted=accepted, reason=reason, referenced_record=subject,
                source_bindings=bindings.get(subject, []))

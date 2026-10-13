"""Narrow personal-action routing, before the generic coding/report queue."""
import re


REMINDER = re.compile(
    r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
    r'(?:create|set(?:\s+up)?|schedule)\s+(?:an?\s+)?'
    r'(?P<kind>reminder|timer|alarm)\b\s*(?P<clause>[\s\S]*)$', re.I)

MORNING = re.compile(
    r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
    r'(?:(?:create|set(?:\s+up)?|schedule)\s+(?:an?\s+)?(?P<kind>routine|reminder|timer|alarm)\s+|(?P<remind>remind me)\s+)?'
    r'every morning(?:\s+at\s+(?P<clock>\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?'
    r'\s+(?P<mode>do|to|remind me to)\s+(?P<body>[\s\S]+)$', re.I)


def routine_request(text):
    return MORNING.fullmatch(text.strip())


def routine_intent(text):
    return bool(re.match(r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
                         r'(?:(?:create|set(?:\s+up)?|schedule)\s+(?:a\s+)?routine\b|every morning\b)',
                         text.strip(), re.I))


def reminder_request(text):
    return REMINDER.fullmatch(text.strip())


def handle(store, text, conversation_id, request_id, *, local_tasks=None, intent_state=None, actor='owner'):
    """A recognized but incomplete action stays here; it never becomes a job."""
    if reminder_request(text) or routine_intent(text):
        return store.handle(text, conversation_id, request_id, local_tasks=local_tasks, intent_state=intent_state, actor=actor)
    return None

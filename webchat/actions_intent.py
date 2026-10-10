"""Narrow personal-action routing, before the generic coding/report queue."""
import re


REMINDER = re.compile(
    r'^(?:(?:please\s+)|(?:(?:can|could|would) you\s+))*'
    r'(?:create|set(?:\s+up)?|schedule)\s+(?:an?\s+)?'
    r'(?P<kind>reminder|timer|alarm)\b\s*(?P<clause>[\s\S]*)$', re.I)


def reminder_request(text):
    return REMINDER.fullmatch(text.strip())


def handle(store, text, conversation_id, request_id):
    """A recognized but incomplete action stays here; it never becomes a job."""
    if reminder_request(text):
        return store.handle(text, conversation_id, request_id)
    return None

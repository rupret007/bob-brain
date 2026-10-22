"""Direct inspection of confirmed Web Bob notes without model reconstruction."""
import re

from memory_store import read_memory

QUESTIONS = frozenset(('my saved memories', 'show my saved memories', 'show saved memory',
    'what do you remember about me', 'what have you saved about me', 'show my memory'))


def matches(text):
    return re.sub(r'\s+', ' ', text.strip().casefold()).rstrip('.?!') in QUESTIONS


def inspect(root, redact):
    try:
        value = read_memory(root, budget=16000)
    except FileNotFoundError:
        return ('No saved Web Bob notes yet. Ask “remember that…” to review a new memory before saving. '
                'Other profile or chat context may still exist.')
    except OSError:
        return 'I could not read saved Web Bob memory reliably. The notes may still exist; nothing was changed.'
    if not value['text'].strip():
        return 'No saved Web Bob notes yet. Other profile or chat context may still exist.'
    # Repeated confirmations may produce identical dated entries. Collapse only
    # exact display duplicates; storage, different dates and distinct facts stay.
    entries = [p.strip() for p in re.split(r'(?=^\[\d{4}-\d{2}-\d{2}\] )', value['text'], flags=re.M) if p.strip()]
    seen, unique = set(), []
    for entry in reversed(entries):
        if entry not in seen:
            unique.append(entry)
            seen.add(entry)
    text = '\n\n'.join(reversed(unique))
    heading = 'Saved Web Bob notes'
    if value['truncated']:
        heading += ' (newest excerpt; older notes are not shown)'
    note = '\nRepeated identical entries are shown once.' if len(unique) < len(entries) else ''
    return (heading + ':\n\n' + redact(text) + note +
            '\n\nThese are confirmed Web Bob notes, not all profile or chat context. '
            'Viewing them does not call a model. Saved notes can be used in later model replies.')

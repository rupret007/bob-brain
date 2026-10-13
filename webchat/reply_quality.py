"""Cheap presentation checks; this module never grants consent or runs work."""
import re


def check(ask, content):
    if re.fullmatch(r'(?:please )?fix it[.!? ]*', ask, re.I) and content.strip() in (
            'What would you like me to work on?', 'Ready when you are.'):
        return "What's broken? Paste the error and tell me what you expected to happen."
    if re.search(r'\bpush everything to the max\b', ask, re.I) and content.strip() == 'Which projects should I work on?':
        stop = ' until midnight' if re.search(r'\buntil midnight\b', ask, re.I) else ''
        return (f'I can propose focused work on your named projects{stop}, keeping existing holds and spending limits. '
                'Which projects and resource limits should I use before you OK the plan?')
    # Preserve quoted material, code, links, identifiers and transport tokens.
    # Technical questions may legitimately ask about the internal vocabulary.
    words = {
        'lifecycle stage': 'status',
        'task record is supplied': 'task details are available',
        'for the handback': 'for your notes',
        'handback': 'saved update',
        'receipt': 'confirmation',
    }
    chunks = re.split(r'(```[\s\S]*?```|`[^`]*`|https?://\S+|\S*/\S+|"[^"\n]*"|“[^”\n]*”)', content)
    for index in range(0, len(chunks), 2):
        for phrase, replacement in words.items():
            if not re.search(r'\b' + re.escape(phrase) + r'\b', ask, re.I):
                chunks[index] = re.sub(r'\b' + re.escape(phrase) + r'\b', replacement, chunks[index], flags=re.I)
        chunks[index] = re.sub(r'unverified because no (.{1,80}?) (?:was |were |is |are )?supplied',
                               r'not confirmed; I do not have \1', chunks[index], flags=re.I)
    return ''.join(chunks)


def spreadsheet_proposal(text):
    return bool(re.match(r'^(?:(?:please|can you|could you)\s+)?(?:make|create|build)\s+(?:me\s+)?'
                         r'(?:a\s+)?(?:simple\s+)?spreadsheet\b', text.strip(), re.I))

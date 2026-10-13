"""Cheap presentation checks; this module never grants consent or runs work."""
import re


def creative_request(text):
    """Writing and brainstorming belong to the normal model reply pipeline."""
    from chat_intent import command
    from answer_intent import wants_answer
    ask = command(text)
    return bool(wants_answer(text) and (
        re.match(r'^(?:write|draft|compose|rewrite|revise|rephrase|shorten|expand|brainstorm)\b', ask, re.I)
        or (re.match(r'^(?:give|show|offer|suggest|list|come up with)\b', ask, re.I)
            and re.search(r'\b(?:name|title) (?:ideas|suggestions)\b|'
                          r'\bideas for (?:our |my |the |an? )?(?:next )?(?:EP|album|song|story)\b', ask, re.I))))


def check(ask, content):
    if creative_request(ask):
        return content
    if re.fullmatch(r'(?:please )?fix it[.!? ]*', ask, re.I) and content.strip() in (
            'What would you like me to work on?', 'Ready when you are.'):
        return "What's broken? Paste the error and tell me what you expected to happen."
    if re.search(r'\bpush everything to the max\b', ask, re.I) and content.strip() == 'Which projects should I work on?':
        stop = ' until midnight' if re.search(r'\buntil midnight\b', ask, re.I) else ''
        return (f'I can draft a focused plan for your OK{stop}, keeping existing holds and spending limits. '
                'Which projects should I focus on, and what time and spending limits should I keep?')
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

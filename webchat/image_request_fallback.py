"""Deterministic text for explicit image requests; no provider or I/O boundary.

This is a text deliverable, not an image job or an action receipt. The caller
owns attachment/worker routing and supplies the saved holds under its lock.
"""
import re

from answer_intent import instructions
from chat_intent import blocked_scopes, command, hold_reply, projects


STYLE = r'(?:watercolou?r|photorealistic|realistic|cinematic|oil painting|pixel art|anime|cartoon|pencil sketch|minimalist|abstract)'
REQUEST = re.compile(
    r'^(?:generate|create|make|produce|draw|paint|render)\s+(?:me\s+)?'
    r'(?:(?:a|an|the)\s+)?(?:(?P<style>' + STYLE + r')\s+)?'
    r'(?P<medium>images?|pictures?|photos?|photographs?|portraits?|illustrations?|'
    r'bitmaps?|rasters?|png|jpe?g|webp|watercolou?r|oil painting|pixel art|pencil sketch|painting|sketch)'
    r'\b(?P<details>.*)$', re.I | re.S)
DRAW = re.compile(r'^(?:draw|paint)\s+(?:me\s+)?(?P<details>.+)$', re.I | re.S)
CODE = re.compile(r'\b(?:svg|code|html|css|javascript|python|canvas|mermaid|ascii|unicode|text art)\b', re.I)
# Only descriptive text is projected. Instructions, destinations and markup
# are never echoed as output links, receipts or purported generated artifacts.
CONTROL = re.compile(
    r'\b(?:and\s+then|then|ignore|pretend|claim|say|tell|report|download|attach\w*|'
    r'upload|send|email|text me|give me|save|write|read|open|use (?:the |my )?(?:key|secret)|'
    r'api|provider|token|secret|password|queued|generated|progress|https?|www)\b|'
    r'[<>`\[\]{}@/\\]|\b\S+\.(?:png|jpe?g|webp|gif|com|org|net)\b', re.I)


def _description(value):
    value = CONTROL.split(value, maxsplit=1)[0]
    value = re.split(r'[.!?](?:\s|$)|;(?!\s*style\s*:)|\n(?!\s*style\s*:)', value,
                     maxsplit=1, flags=re.I)[0]
    value = re.sub(r'\s+', ' ', value)
    value = re.sub(r'[^\w ,.!?;:()\-’\'"–—]', '', value)
    value = re.sub(r'\b(?:and|with|to|at|in|as|a|an|the)\s*$', '', value, flags=re.I)
    return value.strip(' ,.!?;:-')[:240].rstrip()


def reply(text, intent_state):
    """Return a text brief or None for explanation, reference, upload/code intent.

    No deferred execution exists: admission and delivery occur synchronously
    while Chat.submit holds its conversation lock. Never apply a permission
    transition from this request (including any appended approval or retry).
    """
    request = command(instructions(text))
    if not re.match(r'^(?:generate|create|make|produce|draw|paint|render)\b', request, re.I):
        return None
    # The directive must be outside reference text, but a quoted subject is
    # still descriptive input. Sanitization below never executes that input.
    literal = command(text)
    match = REQUEST.fullmatch(literal)
    if not match:
        match = DRAW.fullmatch(literal)
    if not match or CODE.search(literal):
        return None
    if re.match(r'^(?:draw\s+(?:up|conclusions?|comparisons?|parallels?|on|from)|paint\s+(?:over|my|the)\s+wall)\b', request, re.I):
        return None
    if re.match(r'\s*(?:prompt|brief|instructions|tutorial|code|generator|generation)\b', match['details'], re.I):
        return None
    if (re.match(r'^\s*(?:can|could|would|will) you\b', text, re.I)
            and not match['details'].strip(' .!?')):
        return None
    scopes = blocked_scopes(intent_state, projects(request))
    if scopes:
        return hold_reply(scopes)
    details = _description(match['details'])
    details = re.sub(r'^(?:of|showing|depicting)\s+', '', details, flags=re.I)
    details = re.sub(r'^(?:a|an|the)\s+', '', details, flags=re.I)
    style = match.groupdict().get('style') or ''
    medium = match.groupdict().get('medium', '')
    if not style and re.fullmatch(STYLE, medium, re.I):
        style = medium
    explicit_style = re.search(r'(?:[,;]\s*style\s*:|\s+in\s+)(.+?)(?:\s+style)?$', details, re.I)
    if explicit_style and (explicit_style[0].lstrip().lower().startswith((',', ';'))
                           or re.fullmatch(STYLE + r'(?: style)?', explicit_style[1], re.I)):
        style = explicit_style[1].strip()
        details = details[:explicit_style.start()].strip(' ,;')
    return ('Image generation is unavailable here. No image was generated.\n\n'
            'TEXT-ONLY IMAGE BRIEF\n'
            f'Subject: {details or "Not supplied; describe what the image should show."}\n'
            f'Style: {style or "Not specified."}\n\n'
            'This brief is text only. No provider was contacted; nothing was queued, saved as an image, attached, or sent.')

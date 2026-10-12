"""Conservative approval markers, including markers inside requested content.

A match asks for consent or refuses an effect; it does not infer authorization.
False positives are intentional. This pattern is not a natural-language guarantee.
"""
import re


_APPROVAL = re.compile(
    r'\b(?:confirm\w*|approv\w*|permission\w*|consent\w*)\b|'
    r'\breview\w*(?:\s+(?:it|this))?[\s-]+(?:first|only|required|needed)\b|'
    r'\b(?:for|needs?|let\s+me|want\s+to|need\s+to)\s+(?:(?:my|a)\s+)?review\w*\b|'
    r'\bdry[\s-]+run\b|'
    r'\bask\s+(?:me|first|whether|before)\b|\bcheck\s+with\s+me\b|'
    r'\bmy\s+(?:ok(?:ay)?|go[\s-]+ahead|say[\s-]+so)\b|'
    r'\bsay\s+(?:go|yes|ok(?:ay)?)\b|\bwait\s+(?:for|until)\b|'
    r'\bhold\s+off\b|\bnot\s+yet\b|'
    r"\b(?:don't|don’t|do\s+not)\b[^.!?]*\byet\b|"
    r'\buntil\s+I\b|\bbefore\s+(?:you|saving|creating|writing|scheduling)\b|'
    r'\bonly\s+(?:if|after|when|with)\b', re.I)


def approval_requested(text):
    return bool(_APPROVAL.search(text))

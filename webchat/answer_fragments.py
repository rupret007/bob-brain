"""Retain complete independent answer units after a rejected premise.

This is a bounded dependency check, not semantic certification. It never edits
a sentence into a new assertion or grants execution authority. The caller still
checks each original unit against evidence and the user's current constraints.
"""
import re
from reported_records import units, presentation

DEPENDENT = re.compile(r'\b(?:therefore|thus|hence|consequently|accordingly|thereby|'
    r'for (?:this|that) reason|given (?:this|that)|based on (?:this|that|the above)|'
    r'with (?:this|that|those|such)|as a result|it|its|they|their|these|those)\b|'
    r'^\s*(?:so|then|this|that|which|and|but|yet)\b',re.I)
PREPARATION = re.compile(r'^\s*(?:(?:first|next|instead|independently)\s*,?\s*)?'
    r'(?:(?:we|you)\s+(?:should|must|need to)\s+|'
    r'(?:the\s+)?(?:next|first)\s+(?:step|check|action)\s+is\s+to\s+)?'
    r'(?:check|verify|inspect|examine|assess|evaluate|audit|compare|measure|'
    r'prepare|define|outline|draft|write|record|list|match|collect|obtain|assemble)\b',re.I)
QUESTION = re.compile(r'^\s*(?:what|which|how|where|whether)\b',re.I)
ACKNOWLEDGEMENT = re.compile(r"^\s*(?:got it|okay|ok|understood|sure|yes)[\s.!—–,:-]*"
    r"(?:(?:I|we)(?:['’]ll| will)\s+(?:keep|make)\s+(?:it|this|the replies?|my replies?)\s+"
    r"(?:short|brief|concise|friendly)[.!\s]*)?$",re.I)
CAUSAL = re.compile(r'\b(?:therefore|thus|hence|consequently|accordingly|thereby|'
    r'for (?:this|that) reason|given (?:this|that)|based on (?:this|that|the above)|'
    r'with (?:this|that|those|such)|as a result)\b|^\s*(?:so|then)\b',re.I)


def consequence_of_rejected_reference(unit):
    label,body=presentation(unit)
    return bool(CAUSAL.search(label) or CAUSAL.search(body) or re.match(
        r'^\s*(?:it|this|that|they)\b[^.!?]{0,100}\b(?:allows?|authorizes?|permits?|'
        r'means?|proceed|resume|start|run|execute)\b',body,re.I))


def independent_after_rejection(unit):
    label,body=presentation(unit)
    if DEPENDENT.search(body) or DEPENDENT.search(label):
        return False
    return bool(PREPARATION.match(body) or QUESTION.match(body) and body.rstrip().endswith('?'))


def select(content, acceptable, *, pending=False):
    """Return original kept bytes, offset receipts and unresolved dependency."""
    kept=[];decisions=[];offset=0
    for part in units(content):
        valid=bool(acceptable(part))
        dependent=bool(part.strip() and pending and not independent_after_rejection(part))
        accepted=valid and not dependent
        decisions.append(dict(start=offset,end=offset+len(part),accepted=accepted,
                              reason='unsupported_unit' if not valid else
                              'dependent_on_rejected_reasoning' if dependent else 'independent_or_supported'))
        if accepted:
            kept.append(part)
            # A proposed check supplies no result supporting a later causal
            # recommendation. Keep the rejected-premise state for the rest
            # of this answer, while accepting each independent next step.
        elif part.strip():
            pending=True
        offset+=len(part)
    return ''.join(kept),decisions,pending

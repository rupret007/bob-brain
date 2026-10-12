"""Conservative, category-based approval-intent check, not authorization.

This is a pattern/intent check, not a natural-language guarantee. Categories
combine grammatical relationships with semantic word families; they are not a
catalogue of accepted consent sentences. Shared hedges intentionally do not
depend on the verb that follows them ("after I sleep on it", for example).

Ambiguity means ASK. Scan the entire request, including quotes, filenames and
requested content: a putative content boundary must not hide withheld consent.
Negation or a competing instruction never cancels a detected hedge. False
positives are preferable to executing a potentially unapproved effect.
"""
import re
import unicodedata


def _words(expression):
    return re.compile(r'\b(?:' + expression + r')\b')


def _normalize(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    # Treat typographic apostrophes, hyphens, line breaks and repeated spaces
    # alike. Do not discard quoted spans or split away trailing constraints.
    text = ''.join(' ' if unicodedata.category(char) == 'Pd' or char == '_'
                   else "'" if char in '\u2018\u2019\u02bc' else char for char in text)
    return re.sub(r'\s+', ' ', text)


# Shared grammatical signals. In particular, temporal + person/possessor is
# enough to defer; its complement can contain ANY verb, not just "approve".
_PERSONAL = _words(r'i|i\'\w+|me|my|mine|we|us|our|you|your')
_SELF_REQUEST = _words(r'i|i\'\w+|we|let\s+(?:me|us)|give\s+(?:me|us)')
_CONSULT = _words(r'(?:with|to)\s+(?:me|us)|show\w*\s+(?:me|us)')
_PRIORITY = _words(r'first|before|prior|initially')
_RESTRICTION = _words(r'only|just|keep|remain\w*|need\w*|requir\w*|must')
_OWNERSHIP = _words(r'my|our')
_TEMPORAL_PERSON = _words(
    r'(?:after|before|until|once|when|upon)\s+(?:i|we|you|my|our|your|me|us)')
_CONDITION = _words(
    r'if|unless|provided|providing|assuming|conditional\w*|'
    r'on\s+(?:the\s+)?condition|subject\s+to|'
    r'only\s+(?:after|before|when|once|with|upon)')
_NEGATION = _words(r'no|not|nothing|never|without|\w+n\'t|undone|unexecuted|uncommitted')
_UNCERTAINTY = _words(r'maybe|perhaps|possibly|unsure|uncertain\w*|undecided|tentative\w*')

# Semantic vocabulary is shared across sentence shapes. Inflections belong to
# a family; adding a new sentence is not necessary for different word order,
# intervening modifiers, request subjects or objects.
_CONSENT = _words(
    r'confirm\w*|approv\w*|permission\w*|consent\w*|agree\w*|'
    r'authori[sz]\w*|assent\w*|ok(?:ay)?|green\s+light|go\s+ahead|say\s+so|'
    r'sign\s+off|blessing|nod|signal|say\s+(?:go|yes)')
_WAIT = _words(r'wait\w*|await\w*|hold\w*|paus\w*|defer\w*|pending|postpon\w*')
_DECISION = _words(r'decid\w*|decision\w*|deliberat\w*|ponder\w*')
_ASK = _words(r'ask\w*')
_WHETHER = _words(r'whether')
_PREVIEW = _words(r'preview\w*')
_PERCEPTION = _words(r'see|look\w*|check\w*|inspect\w*|examin\w*|peek\w*|view\w*|show\w*')
_REVIEW = _words(
    r'review\w*|scrutini\w*|assess\w*|evaluat\w*|vet|vets|vetted|vetting|audit\w*|'
    r'double\s+check\w*')
_FOR_REVIEW = _words(r'for\s+(?:(?:my|our|a)\s+)?review\w*')
_LOOK_ACTION = _words(r'go|look')
_OVER = _words(r'over')
_DRAFT = _words(r'draft\w*|provisional\w*')
_PROPOSAL = _words(r'propos\w*')
_SIMULATION = _words(
    r'dry\s+run|simulat\w*|pretend\w*|rehears\w*|hypothetic\w*|'
    r'demonstrat\w*|mock\w*|illustrat\w*')
_COUNTERFACTUAL = _words(r'would|could')
_QUESTION = _words(r'what|how')
_EXPLANATION = _words(r'show\w*|explain\w*|walk\w*|describe\w*')
_INCOMPLETE_HEDGE = _words(r'before|until')
_DELAY = _words(r'yet|now')


def _conditional_approval(text):
    return bool(_CONDITION.search(text) or _TEMPORAL_PERSON.search(text))


def _preview_first(text):
    return bool(_PREVIEW.search(text) or
                (_PERCEPTION.search(text) and
                 (_SELF_REQUEST.search(text) or _CONSULT.search(text) or _PRIORITY.search(text))))


def _draft_only(text):
    # Negative language may describe content, but may also prohibit an effect.
    # We cannot safely infer the scope of that negation, so ask in either case.
    return bool(_DRAFT.search(text) or _NEGATION.search(text) or
                (_PROPOSAL.search(text) and _RESTRICTION.search(text)))


def _wait_for_ok(text):
    return bool(_CONSENT.search(text) or _WAIT.search(text) or
                (_NEGATION.search(text) and _DELAY.search(text)) or
                (_DECISION.search(text) and _PERSONAL.search(text)) or
                (_ASK.search(text) and
                 (_PERSONAL.search(text) or _PRIORITY.search(text) or _WHETHER.search(text))))


def _dry_run(text):
    return bool(_SIMULATION.search(text) or
                (_COUNTERFACTUAL.search(text) and _QUESTION.search(text) and _EXPLANATION.search(text)))


def _review_first(text):
    # A review activity alone ("remind me to review notes") is not a hedge.
    # Personal review, required review or review before action is a hedge.
    return bool(_FOR_REVIEW.search(text) or
                (_REVIEW.search(text) and
                 (_SELF_REQUEST.search(text) or _PRIORITY.search(text) or
                  _RESTRICTION.search(text) or _OWNERSHIP.search(text))) or
                (_PERSONAL.search(text) and _LOOK_ACTION.search(text) and _OVER.search(text)))


def _ambiguous_deferral(text):
    # Incomplete hedges still ask. A missing object is not permission, e.g.
    # "before proceeding", "until later", "only after ...", or "maybe".
    return bool(_UNCERTAINTY.search(text) or _INCOMPLETE_HEDGE.search(text))


_DETECTORS = {
    'conditional_approval': _conditional_approval,
    'preview_first': _preview_first,
    'draft_only': _draft_only,
    'wait_for_ok': _wait_for_ok,
    'dry_run': _dry_run,
    'review_first': _review_first,
    'ambiguous_deferral': _ambiguous_deferral,
}


def approval_categories(text):
    """Return overlapping reasons to ASK; an empty result is not a consent grant.

    Callers must still enforce their own routing, holds, exact confirmation,
    allowlists and effect protections. This check must never override those gates.
    """
    normalized = _normalize(text)
    return frozenset(name for name, detector in _DETECTORS.items() if detector(normalized))


def approval_requested(text):
    """Compatibility boundary for parsers: any category requires clarification."""
    return bool(approval_categories(text))

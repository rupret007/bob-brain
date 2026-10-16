"""Conservative, category-based approval-intent check, not authorization.

This is a pattern/intent check, not a natural-language guarantee. Categories
combine grammatical relationships with semantic word families; they are not a
catalogue of accepted consent sentences. Shared hedges intentionally do not
depend on the verb that follows them ("after I sleep on it", for example).
Unresolved clause structure also requires ASK, independently of vocabulary.

Ambiguity means ASK. Scan the entire request, including quotes, filenames and
requested content: a putative content boundary must not hide withheld consent.
Negation or a competing instruction never cancels a detected hedge. False
positives are preferable to executing a potentially unapproved effect.
"""
import re
import unicodedata

from actions_intent import reminder_request, routine_request


def _words(expression):
    return re.compile(r'\b(?:' + expression + r')\b')


# Dots delimit letters within a word; whitespace between single letters may
# also hide word boundaries. That ambiguity requires ASK even after joining.
_DOTTED_LETTERS = re.compile(r'\b[a-z](?:\.[a-z])+(?!\w)')
_SPACED_LETTERS = re.compile(r'\b[a-z](?:[^\S\r\n]+[a-z])+(?!\w)')


def _detection_text(text):
    # Format characters include zero-width spaces/joiners, BOM and soft hyphens.
    # Remove them before compatibility normalization so they cannot split a
    # visible consent word. This copy must never become executable content.
    return unicodedata.normalize('NFKC', ''.join(
        char for char in text if unicodedata.category(char) != 'Cf'))


def _fold_punctuation(text):
    # Fold apostrophes/hyphens without discarding quoted spans or constraints.
    return ''.join(' ' if unicodedata.category(char) == 'Pd' or char == '_'
                   else "'" if char in '\u2018\u2019\u02bc' else char for char in text.casefold())


def _join_dotted(text):
    return _DOTTED_LETTERS.sub(lambda match: match[0].replace('.', ''), text)


def _normalize(text):
    text = _join_dotted(_fold_punctuation(_detection_text(text)))
    text = _SPACED_LETTERS.sub(lambda match: re.sub(r'\s+', '', match[0]), text)
    return re.sub(r'\s+', ' ', text)


# Shared grammatical signals. Temporal prerequisites can have a person,
# gerund, or passive clause as their complement. Do not require an adjacent
# pronoun: the unparsed complement is not evidence of present authorization.
_PERSONAL = _words(r'i|i\'\w+|me|my|mine|we|us|our|you|your')
_SELF_REQUEST = _words(r'i|i\'\w+|we|let\s+(?:me|us)|give\s+(?:me|us)')
_CONSULT = _words(r'(?:with|to)\s+(?:me|us)|show\w*\s+(?:me|us)')
_PRIORITY = _words(r'first|before|beforehand|prior|initially')
_RESTRICTION = _words(r'only|just|keep|remain\w*|leav\w*|retain\w*|preserv\w*|'
                      r'need\w*|requir\w*|must')
_OWNERSHIP = _words(r'my|our')
_PREREQUISITE = _words(r'after|before|until|once|when|upon')
_CONDITION = _words(
    r'if|unless|provided|providing|assuming|suppose|supposing|should|'
    r'conditional\w*|contingent\w*|'
    r'depend\w*\s+(?:on|upon)|'
    r'on\s+(?:the\s+)?condition|subject\s+to|'
    r'only\s+(?:after|before|when|once|with|upon)')
_NEGATION = _words(r'no|not|nothing|never|without|\w+n\'t|undone|un[a-z]+(?:ed|en)')
# Negative-action predicates carry withholding force even without not/never.
# Dictionary words are not evidence of unconditional consent. These families
# also apply inside apparent content: their authorization scope is unresolved.
_INHIBITION = _words(r'avoid\w*|refrain\w*|prevent\w*|suppress\w*|skip\w*|'
                     r'ceas\w*|halt\w*|omit\w*|abstain\w*|stop\w*|disabl\w*|'
                     r'prohibit\w*|forbid\w*|forbade|interdict\w*|proscrib\w*|'
                     r'taboo\w*|tabu(?:s|ed|ing)?|verboten|ban(?:s|ned|ning)?|bar(?:s|red|ring)?|'
                     r'disallow\w*|den(?:y|ies|ied|ying|ial)\w*|refus\w*|reject\w*|'
                     r'veto\w*|embargo\w*|restrict\w*|suspend\w*|withh[oe]ld\w*|'
                     r'revok\w*|rescind\w*|cancel\w*|abort\w*|block\w*|'
                     r'freez\w*|frozen|blacklist\w*|outlaw\w*|impermissib\w*|'
                     r'inadmissib\w*|illicit\w*|illegal\w*|moratori\w*|'
                     r'shelv\w*|desist\w*|forbear\w*|eschew\w*|shun\w*|'
                     r'preclud\w*|inhibit\w*|quash\w*|squelch\w*|repress\w*|'
                     r'resist\w*|withdraw\w*|abandon\w*|discard\w*|scrap\w*|scrub\w*|'
                     r'tabl(?:e|es|ed|ing)|'
                     r'off\s+limits?|out\s+of\s+bounds|hands\s+off')
_UNCERTAINTY = _words(r'maybe|perhaps|possib\w*|potential\w*|probab\w*|may|might|'
                      r'unsure|uncertain\w*|undecided|tentative\w*')

# Semantic vocabulary is shared across sentence shapes. Inflections belong to
# a family; adding a new sentence is not necessary for different word order,
# intervening modifiers, request subjects or objects.
_CONSENT = _words(
    r'confirm\w*|approv\w*|permission\w*|consent\w*|agree\w*|concur\w*|'
    r'authori[sz]\w*|assent\w*|accept\w*|clearance|ok(?:ay)?|green\s+light|go\s+ahead|say\s+so|'
    r'sign(?:s|ed|ing)?\s*offs?|thumbs?\s+up|blessing|nod|signal|say(?:s|ing)?\s+(?:go|yes)')
_FOLLOWS = _words(r'follow(?:s|ing)?')
_WAIT = _words(r'wait\w*|await\w*|hold\w*|paus\w*|defer\w*|pending|postpon\w*')
_DECISION = _words(r'decid\w*|decision\w*|deliberat\w*|ponder\w*|'
                   r'think\w*|thought\w*|consider\w*|reflect\w*|mull\w*')
_ASK = _words(r'ask\w*')
_WHETHER = _words(r'whether')
_PREVIEW = _words(r'preview\w*')
_PERCEPTION = _words(r'see|look\w*|check\w*|inspect\w*|examin\w*|peek\w*|view\w*|show\w*')
_REVIEW = _words(
    r'review\w*|proofread\w*|scrutini\w*|assess\w*|evaluat\w*|vet|vets|vetted|vetting|audit\w*|'
    r'double\s+check\w*')
_CONSULTATION = _words(r'consult\w*|feedback|opinions?|input')
_FOR_REVIEW = _words(r'for\s+(?:(?:my|our|a)\s+)?review\w*')
_LOOK_ACTION = _words(r'go|look')
_OVER = _words(r'over')
_DRAFT = _words(r'draft\w*|provisional\w*')
_PROPOSAL = _words(r'propos\w*|suggest\w*')
_SIMULATION = _words(
    r'dry\s+run|simulat\w*|pretend\w*|rehears\w*|hypothetic\w*|'
    r'demonstrat\w*|mock\w*|illustrat\w*|examples?|thought\s+experiment\w*|'
    r'walkthrough\w*|training|sandbox\w*|'
    r'tutorial\w*|tabletop\w*|imaginar\w*|'
    r'test(?:s|ed|ing)?|trials?|theor(?:y|ies|etic\w*)|conceptual\w*|speculat\w*')
_PRACTICE = _words(r'practic\w*|practis\w*')
_SIMULATION_CONTEXT = _words(r'mode|session|steps|exercise|operation|execution')
_COUNTERFACTUAL = _words(r'would|could')
_QUESTION = _words(r'what|how')
_EXPLANATION = _words(r'show\w*|explain\w*|walk\w*|describe\w*|talk\w*')
_GUIDED_EXPLANATION = _words(r'(?:talk|walk)\w*\s+(?:me|us)\s+through')
_PURPOSE = _words(r'for\s+(?:\w+\s+){0,4}purposes?')
_DISCUSSION = _words(r'discuss\w*|explanat\w*|educat\w*')
_MODE = _words(r'for|as')
_INCOMPLETE_HEDGE = _words(r'before|until')
_DELAY = _words(r'yet|now')
_QUALIFIER = _words(r'but|except\w*|however|although|though|nevertheless')

# A second clause cannot be silently absorbed into arbitrary reminder/file
# content. Coordination and adjuncts have unresolved scope even without any
# punctuation or known consent words. Treat literal content with these shapes
# conservatively too; we cannot prove that it is not an action restriction.
# Filename dots, decimals and clock colons alone are not clause boundaries.
_CLAUSE_BOUNDARY = re.compile(r'[;,\u2013\u2014\r\n\v\f\u0085\u2028\u2029]|[.!?]\s+\S|[()]')
_COORDINATION = _words(r'and|or|nor|then|also|plus')
_ADJUNCT = _words(r'as|in|for|with|by|past|under|on|at')

# The only resolved in/for/on/at adjunct is a time operand. This recognizes syntax,
# not time validity: the scheduling parser must still validate the full request.
# Normalization replaces ISO date hyphens with spaces. Only numeric quantities
# can be resolved here: a word such as "second" may mean a second opinion.
_TIME_OPERAND = re.compile(
    r'\s+(?:'
    r'\d+\s+(?:seconds?|minutes?|mins?|hours?|hrs?|days?)|'
    r'\d{4} \d{2} \d{2}|today|tomorrow|'
    r'\d{1,2}(?::\d{2}\s*(?:am|pm)?|\s*(?:am|pm))'
    r')\b')
# ISO timestamps used after at/on are also explicit operands. Keep this
# separate from the existing in/for grammar; only the newly scanned markers
# need this exception. The scheduling parser still validates the timestamp.
_ISO_OPERAND = re.compile(r'\s+\d{4} \d{2} \d{2}t\d{2}:\d{2}(?::\d{2})?'
                          r'(?:z|[+ ]\d{2}:\d{2})\b')


def _unresolved_structure(text):
    if _COORDINATION.search(text):
        return True
    scheduling = (reminder_request(text) or
                  re.match(r'^(?:remind me|set (?:a )?routine)\b', text))
    # Clock/ISO colons have numeric operands; other scheduling colons may
    # introduce a restriction. File-command colons retain their content syntax.
    if scheduling and re.search(r':(?!\d)', text):
        return True
    morning = routine_request(text)
    for marker in _ADJUNCT.finditer(text):
        # Bare morning syntax resolves only its header clock, never a time
        # modifier in the arbitrary body. Preserve all previous refusals.
        header_clock = (morning and marker[0] == 'at' and
                        marker.start() < morning.start('mode'))
        if ((scheduling or header_clock) and marker[0] in ('in', 'for', 'on', 'at') and
                (_TIME_OPERAND.match(text, marker.end()) or
                 (marker[0] in ('on', 'at') and _ISO_OPERAND.match(text, marker.end())))):
            # Resolve only this marker. Never remove its complement or the
            # remaining text from the semantic or structural scans: a valid
            # time does not license an inline restriction later in the request.
            continue
        return True
    return False


def _conditional_approval(text):
    return bool(_CONDITION.search(text) or _PREREQUISITE.search(text) or
                (_FOLLOWS.search(text) and _CONSENT.search(text)))


def _preview_first(text):
    return bool(_PREVIEW.search(text) or
                (_PERCEPTION.search(text) and
                 (_SELF_REQUEST.search(text) or _CONSULT.search(text) or _PRIORITY.search(text))))


def _draft_only(text):
    # Negative language may describe content, but may also prohibit an effect.
    # We cannot safely infer the scope of that negation, so ask in either case.
    # A proposal or suggestion does not authorize execution, even without
    # "only" or another restriction word. Literal content is ambiguous too.
    return bool(_DRAFT.search(text) or _NEGATION.search(text) or
                _INHIBITION.search(text) or _PROPOSAL.search(text))


def _wait_for_ok(text):
    # A pending decision can be expressed without a person or clause marker.
    # Its scope may be the operation itself, even inside apparent content.
    return bool(_CONSENT.search(text) or _WAIT.search(text) or
                (_NEGATION.search(text) and _DELAY.search(text)) or
                _DECISION.search(text) or
                (_ASK.search(text) and
                 (_PERSONAL.search(text) or _PRIORITY.search(text) or _WHETHER.search(text))))


def _dry_run(text):
    return bool(_SIMULATION.search(text) or
                (_PRACTICE.search(text) and _SIMULATION_CONTEXT.search(text)) or
                _PURPOSE.search(text) or _GUIDED_EXPLANATION.search(text) or
                (_DISCUSSION.search(text) and (_MODE.search(text) or _RESTRICTION.search(text))) or
                (_EXPLANATION.search(text) and _CONSULT.search(text)) or
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
    # Priority, ownership and consultation have unresolved scope even when
    # their complements contain no known decision/consent vocabulary. Do not
    # infer that "first", "my ..." or "... to me" describes harmless content.
    return bool(_UNCERTAINTY.search(text) or _INCOMPLETE_HEDGE.search(text) or
                _QUALIFIER.search(text) or _SELF_REQUEST.search(text) or
                _RESTRICTION.search(text) or _PRIORITY.search(text) or
                _OWNERSHIP.search(text) or _CONSULT.search(text) or
                _CONSULTATION.search(text))


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

    An empty result cannot authorize arbitrary content. Effect callers require
    separate exact confirmation even when no category matches. They also enforce
    their own routing, holds,
    allowlists and effect protections. This check must never override those gates.
    """
    original = unicodedata.normalize('NFKC', text)
    detection_text = _detection_text(text)
    # Keep the previous lexical evidence as well as the joined interpretation.
    # A format character might separate words ("if\u200bthe"), and spelling
    # normalization must not erase an already recognized restriction ("i.s").
    variants = {_normalize(text), re.sub(r'\s+', ' ', _fold_punctuation(original))}
    reasons = {name for name, detector in _DETECTORS.items()
               if any(detector(variant) for variant in variants)}
    # Inspect clause boundaries (including line separators) before whitespace/
    # dash normalization. An unrecognized secondary line must still ASK;
    # flattening it into the body would manufacture authorization. Never strip
    # quoted spans or a putative content suffix from either scan.
    # Spaced letters have ambiguous word boundaries ("i f I a p p r o v e"
    # could collapse to "ifiapprove"). Do not let joining erase a restriction
    # just because its resulting word is absent from the semantic vocabulary.
    if (_CLAUSE_BOUNDARY.search(original) or _CLAUSE_BOUNDARY.search(detection_text) or
            _SPACED_LETTERS.search(_join_dotted(_fold_punctuation(detection_text))) or
            any(_unresolved_structure(variant) for variant in variants)):
        reasons.add('unresolved_clause')
    return frozenset(reasons)


def approval_requested(text):
    """Compatibility boundary for parsers: any category requires clarification."""
    return bool(approval_categories(text))


def leading_approval_request(text, recognize):
    """Recognize a prefixed action only to ask; never strip it for execution.

    Anchored action grammars do not accept "Draft only: create ...". Keep
    those requests in their handler instead of falling through to other work.
    Already recognized requests retain their existing whole-request checks.
    """
    if recognize(text):
        return False
    for word in re.finditer(r'\b\w', text):
        start = word.start()
        if start and recognize(text[start:]) and approval_requested(text[:start]):
            return True
    return False

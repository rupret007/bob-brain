"""Bounded grammatical scope for recommendations, not semantic certification."""
import re

DIRECT_DENIAL = re.compile(r"\b(?:cannot|can['’]t|does not|doesn['’]t|is not|isn['’]t|not|no)\s+(?:(?:be|a|an|any|necessarily|ever|actually|guarantee|establish|imply|prove)\s+){0,3}$", re.I)
NEGATED_COMPLEMENT = re.compile(
    r"\b(?:(?:cannot|can['’]t) (?:assume|promise|guarantee)|(?:does not|doesn['’]t) (?:make|mean|imply|establish|prove)|"
    r"no proof of|no evidence of|rather than (?:assuming|inferring)|without (?:assuming|claiming|promising))\b"
    r"(?:(?!\b(?:guarantee[ds]?|ensures?|therefore|since|because)\b)[^,;:.!?]){0,90}$", re.I)
PREREQUISITE = re.compile(r'\b(?:whether|to (?:check|test|compare|assess|verify|measure|evaluate|qualify)|'
                          r'(?:should|must|need to) (?:check|test|compare|assess|verify|measure|evaluate|qualify))\b[^,;:.!?]{0,100}$', re.I)
VERIFICATION_CONDITION = re.compile(
    r'\b(?:until|unless|if)\s+(?:(?:a|the|representative|bounded|matched)\s+){0,3}'
    r'(?:comparison|evaluation|test|check)\s+(?:establishes|shows|demonstrates|proves|confirms|verifies)\b'
    r'(?:(?!\b(?:guarantee[ds]?|ensures?|therefore|since|because)\b)[^,;:.!?]){0,70}$', re.I)
CONTRAST = re.compile(r'\brather than\s+(?:(?:being|offering|providing|an?|any|completely|truly)\s+){0,3}$', re.I)

# These relations describe scope, not evidence. Callers decide whether a
# negative outcome denies an action or itself promises a protected outcome.
EPISTEMIC_GERUND = re.compile(r'\bwithout\s+(?:assuming|claiming|promising|'
    r'presuming|concluding|asserting|inferring)\b', re.I)
PURPOSE_HEAD = re.compile(r'^(?:preserve|protect|maintain|avoid|prevent|eliminate|'
    r'reduce|limit|guard)\b', re.I)


def negative_passive_effects(text, effect):
    """Yield effect spans governed by one negative passive subject.

    A relative clause or fresh subject ends the relation. Only the immediate
    effect is masked; later predicates, actor claims and receipts remain.
    """
    modifier = (r'(?!(?:that|which|who|whose|where|when|and|or|but|yet|then|'
                r'is|are|was|were|has|have|had|will|would|can|could|may|might|'
                r'because|since|therefore|thus|the|a|an|this|these|those|our|your|my|their|its|his|her|'
                r'of|for|from|with|without|by|under|over|through|in|on|at|'
                r'Codex|Claude|Cursor|Gemini|MiniMax|Bob|'
                r'I|we|you|he|she|it|they)\b)[\w-]+')
    passive = (r'(?:(?:is|are|was|were)\s+(?:being\s+)?|'
               r'(?:has|have|had)\s+been\s+|'
               r'(?:will|would|can|could|may|might)\s+(?:have\s+been|be)\s+)')
    pattern = re.compile(r'\b(?:no|zero|0)\s+(?P<subject>(?:'+modifier+r'\s+){0,10}'
        +modifier+r')\s+'+passive+
        r'(?:(?:yet|ever|actually|already|currently)\s+){0,3}'
        r'(?P<effect>'+effect+r')',re.I)
    for match in pattern.finditer(text):
        from claim_scope import finite_predicate
        if (not finite_predicate(match['subject']) and
                re.search(r'(?:ed|sent|put|picked up|kicked off)$',match['effect'],re.I)):
            yield match.span('effect')


def purpose_governs(prefix):
    """Bind a purpose infinitive to a proposed check, not an asserted ability."""
    to=re.search(r'\bto\s*$',prefix,re.I)
    if not to:return False
    matrix=prefix[:to.start()].strip()
    if not matrix:return True
    from claim_scope import DIRECTIVE, finite_predicate
    directive=DIRECTIVE.match(matrix)
    return bool(directive and not finite_predicate(matrix[directive.end():]))


def nonasserted(prefix, predicate, *, sentence_start=False):
    """Caller supplies one clause; a new affirmative clause cannot inherit scope."""
    if DIRECT_DENIAL.search(prefix) or NEGATED_COMPLEMENT.search(prefix):
        return True
    if predicate.lower().startswith('guarantee'):
        return False
    objective = bool(PURPOSE_HEAD.match(predicate))
    purpose=purpose_governs(prefix)
    if objective and (purpose or
                      sentence_start and re.fullmatch(r'\s*', prefix) and
                      re.match(r'^(?:preserve|protect|maintain)\b',predicate,re.I)):
        return True
    return bool(CONTRAST.search(prefix) or PREREQUISITE.search(prefix) or VERIFICATION_CONDITION.search(prefix))

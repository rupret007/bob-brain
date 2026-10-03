"""Bounded grammatical scope for recommendations, not semantic certification."""
import re

DIRECT_DENIAL = re.compile(r"\b(?:cannot|can['’]t|does not|doesn['’]t|is not|isn['’]t|not|no)\s+(?:(?:be|a|an|any|necessarily|ever|actually|guarantee|establish|imply|prove)\s+){0,3}$", re.I)
NEGATED_COMPLEMENT = re.compile(
    r"\b(?:cannot assume|can['’]t assume|(?:does not|doesn['’]t) (?:make|mean|imply|establish|prove)|"
    r"no proof of|no evidence of|rather than (?:assuming|inferring)|without (?:assuming|claiming|promising))\b"
    r"(?:(?!\b(?:guarantee[ds]?|ensures?|therefore|since|because)\b)[^,;:.!?]){0,90}$", re.I)
PREREQUISITE = re.compile(r'\b(?:whether|to (?:check|test|compare|assess|verify|measure|evaluate|qualify)|'
                          r'(?:should|must|need to) (?:check|test|compare|assess|verify|measure|evaluate|qualify))\b[^,;:.!?]{0,100}$', re.I)
VERIFICATION_CONDITION = re.compile(
    r'\b(?:until|unless|if)\s+(?:(?:a|the|representative|bounded|matched)\s+){0,3}'
    r'(?:comparison|evaluation|test|check)\s+(?:establishes|shows|demonstrates|proves|confirms|verifies)\b'
    r'(?:(?!\b(?:guarantee[ds]?|ensures?|therefore|since|because)\b)[^,;:.!?]){0,70}$', re.I)
CONTRAST = re.compile(r'\brather than\s+(?:(?:being|offering|providing|an?|any|completely|truly)\s+){0,3}$', re.I)


def nonasserted(prefix, predicate, *, sentence_start=False):
    """Caller supplies one clause; a new affirmative clause cannot inherit scope."""
    if DIRECT_DENIAL.search(prefix) or NEGATED_COMPLEMENT.search(prefix):
        return True
    if predicate.lower().startswith('guarantee'):
        return False
    objective = bool(re.match(r'^(?:preserve|protect|maintain) ', predicate, re.I))
    purpose=bool(re.search(r'\bto\s*$', prefix, re.I) and not re.search(
        r'\b(?:proven|guaranteed|certain|known|shown|verified|promised|ensured)\s+to\s*$',prefix,re.I))
    if objective and (purpose or
                      sentence_start and re.fullmatch(r'\s*', prefix)):
        return True
    return bool(CONTRAST.search(prefix) or PREREQUISITE.search(prefix) or VERIFICATION_CONDITION.search(prefix))

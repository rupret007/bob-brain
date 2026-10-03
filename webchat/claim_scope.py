"""Local grammatical scope for protected conclusions, never execution authority.

Presentation and coordinated noun phrases do not create new assertions. A new
finite statement, contrast, or asserted explanation does. This bounded analysis
keeps governors attached to their complements; it does not certify arbitrary
English or infer that a proposed check has already succeeded.
"""
from dataclasses import dataclass
import re

from assertion_scope import nonasserted as local_nonasserted, DIRECT_DENIAL
from reported_records import units

FINITE = re.compile(r"(?<![\w-])(?:am|is|are|was|were|has|have|had|does|do|did|can|could|will|would|"
                    r"should|must|may|might|cannot|can['’]t|won['’]t|guarantees|ensures|"
                    r"preserves|protects|maintains|avoids|prevents|eliminates|incurs|"
                    r"prove[sd]?|establish(?:es|ed)?|confirm[sd]?|demonstrate[sd]?|means|remains|stays|"
                    r"reduce[sd]?|works?|runs?|reads?|access(?:es)?|opens?|offers?|provides?|returns?|points?|"
                    r"guarantee|ensure|preserve|protect|maintain|avoid|prevent|eliminate)(?![\w-])", re.I)
QUESTION = re.compile(r'^\s*(?:who|what|which|where|when|why|how|am|is|are|was|were|'
                      r'has|have|had|do|does|did|can|could|will|would|should|may|might|must)\b', re.I)
DIRECTIVE = re.compile(r'^\s*(?:(?:we|you)\s+(?:should|must|need to)\s+)?'
                       r'(?:check|verify|confirm|inspect|examine|assess|evaluate|compare|'
                       r'measure|test|require|define|outline|specify|prepare|write|record|discuss|choose|decide|'
                       r'preserve|protect|maintain|keep)\b', re.I)
VERIFY = re.compile(r'^\s*(?:(?:we|you)\s+(?:should|must|need to)\s+)?'
                    r'(?:check|verify|confirm|assess|evaluate|measure|test|inspect|examine)\b', re.I)
REQUIRE = re.compile(r'^\s*(?:(?:we|you)\s+(?:should|must|need to)\s+)?require\b', re.I)
COMPLEMENT = re.compile(r'\b(?:whether|that)\s*$', re.I)
DEPENDENT = re.compile(r'\b(?:assume|assuming|claim|claiming|promise|promising|verify|'
                       r'confirm|check|establish|prove|test|assess|evaluate|know|determine)\s*$', re.I)
DENIED = re.compile(r"\b(?:cannot|can['’]t|could not|do not|don['’]t|does not|doesn['’]t|"
                    r"must not|should not|never|not)\s+(?:safely\s+|yet\s+)?"
                    r"(?:assume|claim|promise|guarantee|establish|prove|mean|imply|confirm|verify)\b", re.I)
PASSIVE_UNKNOWN = re.compile(r"\b(?:(?:cannot|can['’]t|could not|must not|should not)\s+be\s+"
    r"(?:assumed|claimed|promised|guaranteed|established|proven|proved|confirmed|verified)|"
    r"(?:is|are|was|were|remain|remains)\s+(?:not\s+(?:assumed|established|known|proven|proved|verified|guaranteed)|"
    r"unknown|unverified|uncertain|unproven))\b", re.I)
NOMINAL_REQUIREMENT = re.compile(r'\b(?:requirements?|criteria|criterion|goals?|objectives?|targets?)'
    r'\s+(?:for|of|to)\b', re.I)
CONNECTOR = re.compile(r',?\s*\b(?:now that|given that|even though|because|since|although|'
                       r'however|therefore|whereas|thus|but|yet|so|then|and|or|while|which|that)\b\s*|,\s*', re.I)
ASSERTED_LINK = re.compile(r'^(?:now that|given that|even though|because|since|although|'
                           r'however|therefore|whereas|thus|but|yet|so|then)$', re.I)
HYPOTHETICAL = re.compile(r'^\s*(?:if|unless|until|when|once|before)\b', re.I)
TERMINAL = re.compile(r'(?<=[.!?;])(?=\s|$)|\n')


def plain(text):
    """Keep offsets stable while removing presentation from grammatical input."""
    text = re.sub(r'[*_`#]', ' ', text)
    return re.sub(r'(?m)^\s*(?:[-+]\s+|\d+[.)]\s+)', lambda m: ' ' * len(m[0]), text)


@dataclass(frozen=True)
class Clause:
    start: int
    end: int
    text: str
    question: bool = False
    label: str = ''


def _coordination(text, *, question=False, base=0, label=''):
    start = 0
    for match in CONNECTOR.finditer(text):
        link = match[0].strip(' ,').lower()
        left = text[start:match.start()]
        right = text[match.end():]
        # Noun-list commas retain a following common predicate/negation.
        left_complete = bool(FINITE.search(left) or DIRECTIVE.match(left) or QUESTION.match(left) or
                             re.match(r'^\s*no\s+',left,re.I))
        next_join = CONNECTOR.search(right)
        immediate = right[:next_join.start()] if next_join and next_join.start() else right
        right_finite = FINITE.search(immediate)
        right_subject = bool(right_finite and right[:right_finite.start()].strip())
        right_question = bool(question and QUESTION.match(right))
        denied = list(DENIED.finditer(left))
        new_subject = (re.match(r'^\s*(?:I|we|you|it|this|that|these|those|the|our|your|my|a|an|all|every|each|any|some)\b',right,re.I)
                       or re.match(r'^\s*[A-Z][\w-]*\b',right))
        plural_subject = bool(right_finite and right_finite[0].lower() in ('are','were') and
                              re.search(r'\b[a-z][\w-]*s\s*$',right[:right_finite.start()]) and
                              not re.match(r'^\s*(?:no|zero|\d+)\b',right,re.I))
        nominal_complement = bool(denied and not FINITE.search(left[denied[-1].end():]) and
                                  right_finite and right_finite[0].lower() in ('are', 'were') and
                                  not new_subject and not plural_subject and ',' not in match[0])
        independent = left_complete and (right_subject or right_question) and not nominal_complement
        relative = link in ('which', 'that') and not DEPENDENT.search(left) and bool(
            right_finite and not right[:right_finite.start()].strip())
        # Bare outcome verbs can share an asserted subject/modal: "the route
        # will reduce demand and preserve quality" is not two directives.
        directives = bool(left_complete and DIRECTIVE.match(right) and
                          (DIRECTIVE.match(left) or not re.match(
                              r'^\s*(?:preserve|protect|maintain|keep|avoid|prevent|eliminate)\b',right,re.I)))
        conditional_end = bool(link == '' and HYPOTHETICAL.match(left))
        discourse = link == '' and re.fullmatch(r'\s*(?:yes|no|well|okay)\s*',left,re.I)
        boundary = bool(ASSERTED_LINK.fullmatch(link) or relative or conditional_end or directives or discourse or
                        link in ('and', 'or', 'while', '') and independent)
        if not boundary:
            continue
        if left.strip():
            yield Clause(base+start, base+match.start(), left,
                         question and bool(QUESTION.match(left)), label)
        # Asserted causal/relative explanations cannot borrow a question or
        # negated assumption from the main clause that precedes them.
        start = match.end()
        label = ''
    if text[start:].strip():
        value = text[start:]
        yield Clause(base+start, base+len(text), value,
                     question and bool(QUESTION.match(value)), label)


def clauses(content):
    """Yield offset-bound local statements without splitting object lists."""
    offset = 0
    for unit in units(content):
        normalized = plain(unit)
        begin = 0
        for boundary in [*TERMINAL.finditer(normalized), None]:
            end = boundary.start() if boundary else len(normalized)
            sentence = normalized[begin:end]
            # A presentation label has its own grammatical scope. Check its
            # words separately; it cannot negate/guarantee the following body.
            title = re.match(r'^\s*([^:\n]{1,128}):\s*', sentence)
            label = ''
            if title and not FINITE.search(title[1]):
                label = title[1].strip()
                yield from _coordination(sentence[:title.end()], base=offset+begin)
                begin += title.end()
                sentence = sentence[title.end():]
            yield from _coordination(sentence, question=sentence.rstrip().endswith('?'),
                                     base=offset+begin, label=label)
            begin = boundary.end() if boundary else len(normalized)
        offset += len(unit)


def disposition(clause, start, end, predicate):
    """Return a nonassertion reason, or None for an unsupported assertion.

    Offsets are relative to this clause. Every sibling statement is classified
    independently, including statements contained inside a question or list.
    """
    text = clause.text
    prefix, suffix = text[:start], text[end:]
    if (not prefix.strip() and re.fullmatch(r'(?:preserving|protecting|maintaining)',predicate,re.I)
            and re.fullmatch(r'[^.!?;]*:\s*',suffix)):
        return 'objective_heading'
    if DIRECT_DENIAL.search(prefix) or DENIED.search(prefix):
        return 'negated_predicate_or_complement'
    nominal_denial = re.match(r'^\s*no\s+(?:guarantee\w*|assurance\w*|promise\w*|'
                             r'evidence|proof|assumption\w*|presumption\w*)\b', text, re.I)
    if nominal_denial:
        return 'negated_nominal_claim'
    for denial in PASSIVE_UNKNOWN.finditer(text):
        # A trailing predicate governs a coordinated subject, not a preceding
        # completed assertion that happens to share the sentence.
        if start < denial.start() and not FINITE.search(text[:denial.start()]):
            return 'unestablished_subject'
    if clause.question:
        return 'question'
    if REQUIRE.match(prefix):
        return 'required_outcome'
    if VERIFY.match(prefix):
        # "Inspect records without charges" attaches an assurance to the
        # inspection. "Check whether it runs without charges" asks a question.
        adjunct = predicate.lower() in ('without', 'no', 'free', 'zero')
        if not adjunct or re.search(r'\bwhether\b', prefix, re.I):
            return 'verification_complement'
    requirement = NOMINAL_REQUIREMENT.search(prefix)
    if requirement and not FINITE.search(prefix[requirement.end():]) and re.fullmatch(
            r'(?:\w+ing|no|zero|free|equal|equivalent)',predicate,re.I):
        return 'requirement_complement'
    # Keep the existing local denial/purpose rules for simple imperatives and
    # uncertainty; coordination above supplies their complete local context.
    scoped = predicate + ' ' if predicate.lower() in ('preserve', 'protect', 'maintain') else predicate
    if local_nonasserted(prefix, scoped, sentence_start=True):
        return 'local_nonassertion'
    if re.search(r'\b(?:may|might|could)\s+(?:(?:help|partly|potentially)\s+)?$', prefix, re.I):
        return 'uncertain_predicate'
    if re.search(r'\b(?:should|must|need to)\s*$', prefix, re.I) and not re.search(r'\b(?:guarantee|ensure)\w*\b', predicate, re.I):
        return 'required_predicate'
    return None

"""Local grammatical scope for protected conclusions, never execution authority.

Presentation and coordinated noun phrases do not create new assertions. A new
finite statement, contrast, or asserted explanation does. This bounded analysis
keeps governors attached to their complements; it does not certify arbitrary
English or infer that a proposed check has already succeeded.
"""
from dataclasses import dataclass
import re

from assertion_scope import nonasserted as local_nonasserted, DIRECT_DENIAL, EPISTEMIC_GERUND
from reported_records import units

FINITE = re.compile(r"(?<![\w-])(?:am|is|are|was|were|has|have|had|does|do|did|can|could|will|would|"
                    r"should|must|may|might|cannot|can['’]t|won['’]t|completed|finished|succeeded|executed|guarantees|ensures|"
                    r"preserves|protects|maintains|avoids|prevents|eliminates|incurs|"
                    r"prove[sd]?|establish(?:es|ed)?|confirm[sd]?|demonstrate[sd]?|means|remains|stays|"
                    r"reduce[sd]?|works?|runs?|reads?|access(?:es)?|opens?|offers?|provides?|returns?|points?|"
                    r"guarantee|ensure|preserve|protect|maintain|avoid|prevent|eliminate)(?![\w-])", re.I)
AUXILIARY = re.compile(r"\b(?:am|is|are|was|were|has|have|had|does|do|did|can|could|will|would|"
                       r"should|must|may|might|cannot|can['’]t|won['’]t)\b",re.I)
QUESTION = re.compile(r'^\s*(?:who|what|which|where|when|why|how|am|is|are|was|were|'
                      r'has|have|had|do|does|did|can|could|will|would|should|may|might|must)\b', re.I)
DIRECTIVE = re.compile(r'^\s*(?:(?:we|you)\s+(?:should|must|need to)\s+)?'
                       r'(?:check|verify|confirm|inspect|examine|assess|evaluate|audit|compare|'
                       r'measure|test|require|define|outline|specify|prepare|write|record|discuss|choose|decide|'
                       r'preserve|protect|maintain|keep)\b', re.I)
VERIFY = re.compile(r'^\s*(?:(?:we|you)\s+(?:should|must|need to)\s+)?'
                    r'(?:check|verify|confirm|assess|evaluate|measure|test|inspect|examine|audit)\b', re.I)
REQUIRE = re.compile(r'^\s*(?:(?:we|you)\s+(?:should|must|need to)\s+)?require\b', re.I)
COMPLEMENT = re.compile(r'\b(?:whether|that)\s*$', re.I)
EPISTEMIC = r'(?:assume|claim|promise|guarantee|establish|prove|mean|imply|confirm|verify|know|determine|conclude)'
DEPENDENT = re.compile(r'\b(?:'+EPISTEMIC+r'|assuming|claiming|promising|check|test|assess|evaluate)\s*$', re.I)
DENIED = re.compile(r"\b(?:cannot|can['’]t|could not|do not|don['’]t|does not|doesn['’]t|"
                    r"must not|should not|never|not)\s+(?:safely\s+|yet\s+)?"
                    + EPISTEMIC + r"\b", re.I)
PASSIVE_UNKNOWN = re.compile(r"\b(?:(?:cannot|can['’]t|could not|must not|should not)\s+be\s+"
    r"(?:assumed|claimed|promised|guaranteed|established|proven|proved|confirmed|verified)|"
    r"(?:is|are|was|were|remain|remains)\s+(?:not\s+(?:assumed|established|known|proven|proved|verified|guaranteed)|"
    r"unknown|unverified|uncertain|unproven))\b", re.I)
NOMINAL_REQUIREMENT = re.compile(r'\b(?:requirements?|criteria|criterion|goals?|objectives?|targets?)'
    r'\s+(?:for|of|to)\b', re.I)
NOMINAL_DENIAL = re.compile(r'\b(?:no|not|neither)\s+(?:proof|evidence|assurance|confirmation|verification)\s+(?:that|of)\b',re.I)
CONNECTOR = re.compile(r',?\s*\b(?:now that|given that|even though|because|since|although|'
                       r'however|therefore|whereas|thus|but|yet|so|then|and|or|while|which|that)\b\s*|,\s*', re.I)
ASSERTED_LINK = re.compile(r'^(?:now that|given that|even though|because|since|although|'
                           r'however|therefore|whereas|thus|but|yet|so|then)$', re.I)
HYPOTHETICAL = re.compile(r'^\s*(?:if|unless|until|when|once|before)\b', re.I)
TERMINAL = re.compile(r'(?<=[.!?;])(?=\s|$)|\n')
WH = re.compile(r'^\s*(?:who|what|which|where|when|why|how)\b', re.I)
# Bare access/read/run/return can be nominal heads in a wh subject. An auxiliary
# or an unambiguous lexical predicate completes that subject; its wh head alone
# does not. This is a bounded grammar, not a general English parser.
WH_PREDICATE = re.compile(r'\b(?:guarantees?|ensures?|preserves?|protects?|maintains?|'
    r'avoids?|prevents?|eliminates?|incurs?|means|remains|stays|'
    r'establish(?:es|ed)?|demonstrates?|confirms?|proves?|shows?|indicates?)\b', re.I)
DECLARATIVE = re.compile(r'\b(?:shows?|showed|indicates?|indicated|suggests?|asserts?)\b',re.I)
PURPOSE = re.compile(r'\bto\s+(?:check|verify|confirm|inspect|examine|assess|evaluate|audit|'
    r'measure|test|ensure|establish|prove|demonstrate|preserve|protect|maintain|avoid|prevent|eliminate|reduce|limit|guard)\b',re.I)
STRONG_FINITE = re.compile(r'\b(?:(?:guarantee|ensure|confirm|prove|establish|demonstrate)s?|'
    r'(?:is|are|was|were|will be|has been|have been)\s+'
    r'(?:guaranteed|proven|proved|confirmed|established|verified|known))\b',re.I)


def purpose_boundary(text):
    """Return (has governed purpose, independent stronger predicate)."""
    purpose = PURPOSE.search(text)
    if not purpose or finite_predicate(text[:purpose.start()]):
        return False, None
    for match in STRONG_FINITE.finditer(text,purpose.end()):
        prefix = text[purpose.end():match.start()]
        # A stronger predicate needs its own explicit question/denial. The
        # mere presence of an earlier infinitive is not that governor.
        own_check = (VERIFY.match(purpose[0].split(None,1)[1]) and re.match(r'^\s*(?:whether|that)\b',prefix,re.I)
                     or re.search(r'\b(?:check|verify|confirm|assess|evaluate|test)\s+(?:whether|that)\b',prefix,re.I))
        if own_check or DIRECT_DENIAL.search(prefix) or DENIED.search(prefix) or re.search(r'\bto\s*$',prefix,re.I):
            continue
        return True, match
    return True, None


def finite_predicate(text, *, purpose=False):
    """Find a finite head, not a nominal access/return or infinitive purpose."""
    if purpose:
        governed, boundary = purpose_boundary(text)
        if governed:
            return boundary
    for match in sorted([*FINITE.finditer(text),*DECLARATIVE.finditer(text)],key=lambda m:m.start()):
        if re.search(r'\bto\s*$',text[:match.start()],re.I):
            continue
        nominal = match[0].lower() in ('access','read','work','run','return','points')
        actor = re.search(r'\b(?:I|we|you|they|he|she|it)\s*$',text[:match.start()],re.I)
        plural_subject = re.fullmatch(r'\s*(?:(?:the|our|your|these|those|some|all)\s+)?'
                                      r'(?:[\w’\'-]+\s+)*[\w’\'-]+s\s*',text[:match.start()],re.I)
        if nominal and not (actor or plural_subject):
            continue
        return match
    return None


def question_complete(text):
    wh = WH.match(text)
    if not wh:
        return bool(finite_predicate(text))
    if AUXILIARY.search(text):
        return True
    for predicate in WH_PREDICATE.finditer(text):
        # In "which guarantees and safeguards...", guarantees is a nominal
        # head. A lexical predicate needs a subject and its complement.
        subject = text[wh.end():predicate.start()].strip()
        complement = text[predicate.end():].strip(' ,.!?')
        if complement and (subject or wh[0].strip().lower() in ('who','what')):
            return True
    return False


def verification_governs(prefix):
    """An imperative governs a check; a nominal audit's result does not."""
    directive = VERIFY.match(prefix)
    if not directive:
        return False
    remainder = prefix[directive.end():]
    complement = re.search(r'\b(?:whether|that|to\s+(?:check|verify|confirm|ensure|'
                           r'establish|assess|evaluate|measure|test|inspect|examine))\b',remainder,re.I)
    subject = remainder[:complement.start()] if complement else remainder
    return not finite_predicate(subject)


def plain(text):
    """Keep offsets stable while removing presentation from grammatical input."""
    text = re.sub(r'\[(?:report|fact):[^\]\n]+\]',lambda m:m[0].replace(':',' '),text)
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
        left_complete = bool(FINITE.search(left) or DIRECTIVE.match(left))
        if WH.match(left):
            left_complete = question_complete(left)
        # Lexical verbs can be noun heads or participial modifiers here:
        # "No completed cost reports ..." still awaits its common predicate.
        if re.match(r'^\s*(?:no|neither)\b',left,re.I) and not AUXILIARY.search(left):
            left_complete=False
        next_join = CONNECTOR.search(right)
        immediate = right[:next_join.start()] if next_join and next_join.start() else right
        directive = DIRECTIVE.match(left)
        object_list = bool(directive and not finite_predicate(left[directive.end():]) and
                           not re.search(r'\b(?:whether|that)\b',left,re.I))
        bare_object = not re.match(r'^\s*(?:I|we|you|they|he|she|it|this|that|the|our|your|my|a|an)\b',right,re.I)
        right_finite = finite_predicate(immediate,purpose=object_list and (bare_object or ',' not in match[0]))
        right_subject = bool(right_finite and right[:right_finite.start()].strip())
        right_question = bool(question and QUESTION.match(right))
        denied = list(DENIED.finditer(left))
        new_subject = (re.match(r'^\s*(?:I|we|you|it|this|that|these|those|the|our|your|my|a|an|all|every|each|any|some)\b',right,re.I)
                       or re.match(r'^\s*[A-Z][\w-]*\b',right))
        # A negative quantified noun list still needs its common predicate:
        # "No prices, fees, or rankings can be determined" is one denial.
        # A fresh determiner/actor instead introduces an independent subject,
        # including after an elliptical "No evidence ..." statement.
        explicit_subject=re.match(r'^\s*(?:I|we|you|it|this|that|these|those|the|our|your|my|a|an|all|every|each|any|some)\b',right,re.I)
        nominal_negative=re.match(r'^\s*no\s+(?:evidence|proof|assurances?|guarantees?|promises?)\b',left,re.I)
        if re.match(r'^\s*(?:no|neither)\b',left,re.I) and (explicit_subject or nominal_negative and new_subject):
            left_complete = True
        plural_subject = bool(right_finite and right_finite[0].lower() in ('are','were') and
                              re.search(r'\b[a-z][\w-]*s\s*$',right[:right_finite.start()]) and
                              not re.match(r'^\s*(?:no|zero|\d+)\b',right,re.I))
        epistemic_boundary=bool(EPISTEMIC_GERUND.search(left) and (
            right_subject and (new_subject or plural_subject or ',' in match[0]) or
            right_finite and not right[:right_finite.start()].strip() or
            DIRECTIVE.match(right) or re.match(r'^\s*(?:use|run|retain|switch|continue|'
                r'guarantee|ensure|avoid|prevent|eliminate)\b',right,re.I)))
        if epistemic_boundary:left_complete=True
        nominal_complement = bool(denied and not FINITE.search(left[denied[-1].end():]) and
                                  right_finite and right_finite[0].lower() in ('are', 'were') and
                                  not new_subject and not plural_subject and ',' not in match[0])
        # Repeated complementizers coordinate propositions under the same
        # denied evidence head: "not proof that A ran or that B finished".
        coordinated_denial = bool(NOMINAL_DENIAL.search(left) and link in ('and','or') and
                                  re.match(r'^\s*that\b',right,re.I))
        # A malformed/elliptical question cannot shield a separate statement
        # introduced by a comma and a new actor.
        explicit_actor = re.match(r'^\s*(?:I|we|you|they|he|she|it)\b',right,re.I) or re.match(r'^\s*[A-Z][\w-]*\b',right)
        indicative_subject = explicit_subject and right_finite and not re.fullmatch(
            r'can|could|will|would|should|must|may|might',right_finite[0],re.I)
        question_boundary = question and WH.match(left) and ',' in match[0] and (explicit_actor or indicative_subject)
        independent = (left_complete or question_boundary) and (right_subject or right_question) and not (nominal_complement or coordinated_denial)
        relative = bool(left.strip()) and link in ('which', 'that') and not DEPENDENT.search(left) and bool(
            right_finite and not right[:right_finite.start()].strip())
        # Bare outcome verbs can share an asserted subject/modal: "the route
        # will reduce demand and preserve quality" is not two directives.
        directives = bool(left_complete and DIRECTIVE.match(right) and
                          (DIRECTIVE.match(left) or not re.match(
                              r'^\s*(?:preserve|protect|maintain|keep|avoid|prevent|eliminate)\b',right,re.I)))
        conditional_end = bool(link == '' and HYPOTHETICAL.match(left))
        discourse = link == '' and re.fullmatch(r'\s*(?:yes|no|well|okay)\s*',left,re.I)
        result_adjunct=bool(link=='' and left_complete and re.match(r'^\s*(?:(?:with\s+(?:[\w-]+\s+){1,6})?'
            r'(?:guaranteeing|ensuring|making|leaving)|thereby)\b',right,re.I))
        boundary = bool(epistemic_boundary or ASSERTED_LINK.fullmatch(link) or relative or conditional_end or directives or discourse or result_adjunct or
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


def disposition(clause, start, end, predicate, *, copular=False):
    """Return a nonassertion reason, or None for an unsupported assertion.

    Offsets are relative to this clause. Every sibling statement is classified
    independently, including statements contained inside a question or list.
    """
    text = clause.text
    prefix, suffix = text[:start], text[end:]
    for governor in EPISTEMIC_GERUND.finditer(text):
        # Match the complete governor even when the protected token is
        # "without" itself. Clause splitting keeps independent assertions
        # separate; a second manner/cost adjunct cannot borrow the denial.
        if start < governor.start() or start>=governor.end() and predicate.lower()=='without':
            continue
        complement=text[governor.end():start]
        following=text[governor.end():]
        first_finite=finite_predicate(following)
        explicit_subject=re.match(r'^\s*(?:that\s+)?(?:the|a|an|our|your|my|their|its|his|her|'
                                  r'this|these|those|I|we|you|he|she|it|they)\b',following,re.I)
        # Finite complements need an explicit complementizer or subject
        # constituent. Ambiguous unpunctuated nominal+matrix sequences do
        # not receive a blanket negation exemption.
        if first_finite and governor.end()+first_finite.start()<=start and not explicit_subject:
            return None
        # An unpunctuated matrix subject can follow a complete nominal
        # complement. A subject at the start of the complement itself still
        # belongs to the denied assumption ("without assuming we ...").
        for subject in re.finditer(r'\b(?:I|we|you|he|she|it|they|this|that|these|those|'
                r'the|a|an|[A-Z][\w-]*)\b',text[governor.end():]):
            before=text[governor.end():governor.end()+subject.start()].strip()
            if not before or before.lower()=='that':continue
            if (explicit_subject and first_finite and subject.start()<first_finite.start() and
                    re.fullmatch(r'[A-Z][\w-]*',subject[0]) and subject[0]!='I'):
                continue
            matrix=text[governor.end()+subject.start():]
            finite=finite_predicate(matrix)
            if (finite and governor.end()+subject.start()+finite.start()<=start and
                    not re.search(r'\b(?:of|for|from|with|without|by|in|on|at|to)\s*$',before,re.I)):
                return None
        if not re.search(r'\b(?:without|by|through|thereby|because|since|therefore|thus)\b',complement,re.I):
            return 'negated_epistemic_governor'
    # A denied conclusion can have a nominal head and support verb. Its
    # comparison complement is unestablished; an attached cost prerequisite
    # ("without incurring charges") is a separate claim, not that conclusion.
    nominal_knowledge = re.match(r'^\s*no\s+(?:determination|conclusion|ranking|comparison|'
        r'judgment|judgement|assessment|inference|finding)\s+'
        r'(?:(?:can|could)\s+be|is|was)\s+(?:made|drawn|established|reached|formed)\b',text,re.I)
    if nominal_knowledge:
        if start < nominal_knowledge.end():
            return 'denied_epistemic_head'
        complement = re.match(r'\s+(?:regarding|about|as to|on)\s+|\s+(?=whether\b|which\b|what\b)',
                              text[nominal_knowledge.end():],re.I)
        if complement:
            # A prepositional circumstance of making the determination does
            # not inherit the denied conclusion. Keep noun coordination in
            # the complement; stop before an attached cost/manner condition.
            embedded=text[nominal_knowledge.end()+complement.end():]
            # An explicit whether/which proposition retains its internal noun
            # modifiers. Independent assertions have their own clause above.
            question_complement=bool(re.match(r'^\s*(?:whether|which|what|how)\b',embedded,re.I))
            adjunct = None if question_complement else re.search(r'\b(?:at|for|from|under|over|on|in|without|with|by|despite|while|'
                                r'using|through|via|during|after|before|upon|within|outside|beyond)\b',
                                embedded,re.I)
            boundary = nominal_knowledge.end()+complement.end()+adjunct.start() if adjunct else len(text)
            if end <= boundary:
                return 'denied_epistemic_complement'
    if (not prefix.strip() and re.fullmatch(r'(?:preserving|protecting|maintaining)',predicate,re.I)
            and re.fullmatch(r'[^.!?;]*:\s*',suffix)):
        return 'objective_heading'
    # A protected match may itself start at "cannot". Read its complete
    # epistemic governor before deciding that it promises a negative outcome.
    if (DIRECT_DENIAL.search(prefix) or DENIED.search(prefix) or
            any(m.start() <= start < m.end() for m in DENIED.finditer(text))):
        return 'negated_predicate_or_complement'
    if NOMINAL_DENIAL.search(prefix):
        return 'negated_evidence_complement'
    dependency = r'\b(?:depends?\s+(?:\w+ly\s+)?on|requires?|is contingent on|is conditional on)\b'
    if (not prefix.strip() and re.fullmatch(r'\w+ing', predicate.split()[0], re.I) and
            re.search(dependency, suffix, re.I)):
        governor = re.search(dependency, suffix, re.I)
        # "Avoiding costs" can be the subject of a dependency; "avoiding
        # costs guarantees quality" still has an asserted outcome predicate.
        if not FINITE.search(suffix[:governor.start()]):
            return 'outcome_dependency_subject'
    nominal_denial = re.match(r'^\s*no\s+(?:guarantee\w*|assurance\w*|promise\w*|'
                             r'evidence|proof|assumption\w*|presumption\w*)\b', text, re.I)
    if nominal_denial:
        return 'negated_nominal_claim'
    quantified = re.match(r'^\s*(?:no|neither)\b', text, re.I)
    epistemic = re.search(r'\b(?:(?:can|could)\s+be|is|are|was|were)\s+'
                          r'(?:known|determined|established|concluded|inferred|verified|confirmed)\b',text,re.I)
    if quantified and epistemic and start<=epistemic.end() and not AUXILIARY.search(text[:epistemic.start()]):
        return 'negative_quantified_knowledge'
    for denial in PASSIVE_UNKNOWN.finditer(text):
        # A trailing predicate governs a coordinated subject, not a preceding
        # completed assertion that happens to share the sentence.
        if start < denial.start() and not FINITE.search(text[:denial.start()]):
            return 'unestablished_subject'
    if clause.question:
        return 'question'
    if REQUIRE.match(prefix):
        return 'required_outcome'
    if verification_governs(prefix):
        # "Inspect records without charges" attaches an assurance to the
        # inspection. "Check whether it runs without charges" asks a question.
        adjunct = predicate.lower() in ('without', 'no', 'free', 'zero')
        if not adjunct or re.search(r'\bwhether\b', prefix, re.I):
            return 'verification_complement'
    if copular:
        # Keep the modal/epistemic governor visible when the predicate is an
        # adjectival state rather than a lexical outcome verb.
        link = r'(?:(?:be|been|being|remain(?:s|ed)?|stay(?:s|ed)?)\s+)?'
        adverbs = r'(?:(?:\w+ly|still|not)\s+)*'
        if re.search(r"\b(?:cannot|can['’]t|won['’]t|not|never)\s+"+adverbs+link+adverbs+r'$',prefix,re.I):
            return 'negated_state'
        if re.search(r'\b(?:may|might|could)\s+'+adverbs+link+adverbs+r'$',prefix,re.I):
            return 'uncertain_state'
        if re.search(r'\b(?:should|must|need(?:s)? to|(?:is|are) required to)\s+'
                     +adverbs+link+adverbs+r'$',prefix,re.I):
            return 'required_state'
        if re.search(r'\b(?:not|never)\s+(?:known|proven|shown|established|verified)\s+to\s+'
                     +link+adverbs+r'$',prefix,re.I):
            return 'unestablished_state'
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

"""Bind grammatical hold references to saved permissions, never grant effects."""
import re

OPERATIONAL_NOUN = r'(?:work|projects?|workers?|jobs?|tasks?|services?|systems?|agents?|processes|daemons?)'
QUANTIFIED = r'(?:(?:all|every|each)\s+(?:(?:of|the|our|your|active|existing|current)\s+)*'+OPERATIONAL_NOUN+r'|everything)'
GLOBAL_REFERENCE = re.compile(
    r'\bglobal\s+hold\b|\b'+QUANTIFIED+r'\s+(?:(?:is|are|was|were|remains?|stays?)\s+|:\s*)'
    r'(?:(?:now|still|currently)\s+)*(?:held|paused|on hold|under\s+(?:the|your|this)\s+hold)\b|'
    r'\bhold\s+(?:(?:still\s+)?appl(?:ies|ying)\s+to|covers?|on|for|in)\s+'+QUANTIFIED+r'\b', re.I)

# Planning actions can be coordinated noun phrases. A gerund alone is not
# evidence of a completed action; execution verbs do not enter this grammar.
PLANNING_ACTION = r'(?:choosing|selecting|deciding|defining|specifying|approving|planning|preparing|comparing|reviewing|identifying|determining|checking|verifying|assessing|evaluating)'
PENDING_HEAD = re.compile(
    r'^\s*(?:'+PLANNING_ACTION+r'\b|'
    r'(?:(?:the|your|our|this|a)\s+)?(?:(?:next|remaining|pending|unresolved)\s+)+'
    r'(?:decision|choice|question|step|requirement)\s+(?:is|remains?|involves?)\s+(?:to\s+\w+|'+PLANNING_ACTION+r')\b)', re.I)
RELATION = re.compile(r'\b(?:under|within|during|subject to|respecting|honou?ring|observing|preserving|maintaining)\s*$', re.I)
NOUN_REFERENCE = re.compile(r'(?:your|the|earlier|previous)\s+(?:(?:earlier|previous|existing|current)\s+)?hold', re.I)
JOINS = re.compile(r'\b(?:because|since|while|whereas|although|even though|given that|now that|and|or|but|yet|however|which|that|who|where)\b|,', re.I)
OBJECT_JOIN = frozenset(('and', 'or', ','))
# Finite state/operation and causative predicates can introduce a claim about
# who is held even without an auxiliary ("falls under", "keeps X under").
# This is a bounded grammatical vocabulary, not a general English parser.
HOLD_PREDICATE = re.compile(r"(?<![\w-])(?:fall(?:s|ing)?|fell|fallen|operat(?:e[sd]?|ing)|"
    r"leav(?:e[sd]?|ing)|left|keep(?:s|ing)?|kept|plac(?:e[sd]?|ing)|put(?:s|ting)?|"
    r"sit(?:s|ting)?|sat|li(?:e[sd]?|es)|lain|remain(?:s|ed)?|stay(?:s|ed)?|"
    r"function(?:s|ed)?|exist(?:s|ed)?|stand(?:s|ing)?|stood|rest(?:s|ed)?|"
    r"continu(?:e[sd]?|ing)|belong(?:s|ed)?|adher(?:e[sd]?|ing)|"
    r"await(?:s|ed)?|wait(?:s|ed)?|govern(?:s|ed)?|bind(?:s|ing)?|bound|"
    r"constrain(?:s|ed)?|cover(?:s|ed)?|appl(?:y|ies|ied))(?![\w-])",re.I)
NOUN_OR_VERB = frozenset('fall falls leave leaves place places put puts sit sits lie lies '
    'function functions stand stands rest rests wait waits work works run runs cover covers'.split())
REFERENTIAL_SUBJECT = re.compile(r'^\s*(?:I|we|you|it|they|he|she|this|that|these|those)\b|'
    r'\b(?:the|a|an|our|your|my|all|every|each|any|some)\s+\S+',re.I)


def planning_governor(prefix, head, finite, projects, worker_names):
    """Retain nominal coordination, without borrowing an asserted predicate.

    A causal, temporal or relative clause needs a new planning governor or a
    direct dependent relation. Keep objects intact; operational nouns alone
    cannot tell a subject from a modifier (e.g. resource requirements).
    """
    from claim_scope import AUXILIARY
    def predicate(text):
        for match in [*finite.finditer(text),*HOLD_PREDICATE.finditer(text)]:
            before,after=text[:match.start()].strip(),text[match.end():].strip()
            if re.search(r'\bto\s*$',before,re.I):
                continue  # An infinitive is still governed by the pending choice.
            if match[0].lower() in NOUN_OR_VERB:
                # A bare head or compound object ("service functions") keeps
                # its planning governor. A referential subject or transitive
                # complement instead exposes a predicate. Ambiguous definite
                # attachments stay unsupported; nouns are not blanket vetoes.
                named=bool(projects(before) or any(re.search(r'\b'+re.escape(name)+r'\b',before,re.I)
                                                  for name in worker_names))
                last=re.search(r'\b([a-z][\w-]*)\s*$',before,re.I)
                plural=bool(last and last[1].lower().endswith('s') and
                            not last[1].lower().endswith(('ss','is','us')))
                # "services function" has plural subject/base verb agreement;
                # "service functions" can instead be a compound noun object.
                agreement=plural and not match[0].lower().endswith('s')
                if not before or not after and not (REFERENTIAL_SUBJECT.search(before) or named or agreement):
                    continue
            return True
        return False

    # A modal purpose describes the aim of a pending choice, not an achieved
    # effect. Remove it from attachment analysis only before a direct dependent
    # relation; the caller still checks effects over the complete original text.
    purpose=re.search(r'\bso(?:\s+that)?\s+(.+?)\bwhile\s*(?:(?:[a-z]+ly|still|always)\s+)*$',prefix,re.I)
    if purpose:
        modal=AUXILIARY.search(purpose[1])
        if (modal and modal[0].lower() in ('can','could','may','might','would') and
                not JOINS.search(purpose[1]) and not HOLD_PREDICATE.search(purpose[1][:modal.start()])):
            prefix=prefix[:purpose.start()]+' '*(len(prefix)-purpose.start())
    joins=list(JOINS.finditer(prefix,head.end()))
    if not joins:
        return not predicate(prefix[head.end():])
    spans=[prefix[head.end():joins[0].start()]]
    for index, join in enumerate(joins):
        end=joins[index+1].start() if index+1<len(joins) else len(prefix)
        local=prefix[join.end():end]
        coordinated=PENDING_HEAD.match(local)
        if coordinated:
            local=local[coordinated.end():]
        elif re.fullmatch(r'\s*(?:(?:[a-z]+ly|still|always)\s+)*',local,re.I):
            continue
        elif join[0].lower() not in OBJECT_JOIN:
            return False
        spans.append(local)
    return not any(predicate(local) for local in spans)


def pending_reference(part, state, scopes, hold_claim):
    """A pending choice may refer to its matching existing hold as a constraint.

    Keep its nominal coordination and dependent purpose intact. Every hold
    mention must be a bound noun reference, with no asserted state or relative
    result attached. Caller independently rejects effects/permission changes.
    """
    from chat_intent import blocked_scopes, projects
    from reported_records import presentation, foreign_label
    from worker_activity import WORKER_NAMES
    from claim_scope import FINITE
    label, body = presentation(part)
    head=PENDING_HEAD.match(body)
    if not scopes or not head or foreign_label(label,projects,WORKER_NAMES):
        return False
    global_hold=state['holds'].get('all')
    if GLOBAL_REFERENCE.search(body) and (not global_hold or global_hold.get('released_projects')):
        return False
    # A new finite subject does not borrow the pending nominal governor.
    independent=re.compile(r'\b(?:and|but|yet|however)\s+(?:(?:I|we|you|it|they)|'
        r'(?:(?:the|a|an|our|your|all|every)\s+)?[\w-]+(?:\s+[\w-]+){0,3})\s+'
        r'(?:is|are|was|were|has|have|had|remains?|stays?|will|did)\b',re.I)
    if independent.search(body):return False
    matches=list(hold_claim.finditer(body))
    if not matches:return False
    for match in matches:
        relation=RELATION.search(body[:match.start()])
        if not NOUN_REFERENCE.fullmatch(match[0]) or not relation:
            return False
        if not planning_governor(body[:relation.start()],head,FINITE,projects,WORKER_NAMES):
            return False
        tail=body[match.end():]
        target=re.match(r'\s+(?:on|for|in)\s+(.+)',tail,re.I)
        if target:
            named=projects(target[1])
            bound=next((re.match(re.escape(name)+r'\b',target[1],re.I) for name in named
                        if blocked_scopes(state,[name]) and re.match(re.escape(name)+r'\b',target[1],re.I)),None)
            if not bound:return False
            tail=target[1][bound.end():]
        # A relative outcome or fresh subject cannot hide behind the referent.
        if tail.strip(' .!?\n'):return False
    return True

"""Retain complete independent answer units after a rejected premise.

This is a bounded dependency check, not semantic certification. It never edits
a sentence into a new assertion or grants execution authority. The caller still
checks each original unit against evidence and the user's current constraints.
"""
import re
from dataclasses import dataclass
from reported_records import units, presentation, ITEM

DEPENDENT = re.compile(r'\b(?:therefore|thus|hence|consequently|accordingly|thereby|'
    r'for (?:this|that) reason|given (?:this|that)|based on (?:this|that|the above)|'
    r'with (?:this|that|those|such)|as a result|it|its|they|their|these|those)\b|'
    r'^\s*(?:so|then|this|that|which|and|but|yet)\b',re.I)
PREPARATION = re.compile(r'^\s*(?:(?:first|next|instead|independently)\s*,?\s*)?'
    r'(?:(?:we|you)\s+(?:should|must|need to)\s+|'
    r'(?:the\s+)?(?:next|first)\s+(?:step|check|action)\s+is\s+to\s+)?'
    r'(?:check|verify|inspect|examine|assess|evaluate|audit|compare|measure|'
    r'prepare|define|outline|draft|write|record|list|match|collect|obtain|assemble|'
    r'request|issue|introduce|ask|instruct)\b',re.I)
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


def heading_unit(unit):
    """A section title is not a consequence of a prior rejected claim."""
    text = unit.strip()
    if not text:
        return False
    # A prospective if/once/after governor ends with a colon but is not a heading.
    if re.match(r'^\s*(?:once|if|when|after)\b', text, re.I):
        return False
    label, body = presentation(unit)
    if label and not body.strip():
        return True
    if re.match(r'^#{1,6}\s+\S', text):
        return True
    return bool(re.fullmatch(r'(?:\*\*[^*\n]{1,80}\*\*|__[^_\n]{1,80}__)[:\s]*', text))


def continues_rejected_clause(unit):
    """Only fragments that continue the rejected clause are dependent on it."""
    _, body = presentation(unit)
    return bool(re.match(r'^\s*(?:and|but|yet|which|or)\b', body, re.I))


def depends_on_rejected_unit(unit, *, pending):
    """Independent list items, headings and sentences are judged on their own."""
    if not pending or not unit.strip() or heading_unit(unit):
        return False
    return consequence_of_rejected_reference(unit) or continues_rejected_clause(unit)


def independent_after_rejection(unit):
    label,body=presentation(unit)
    # A pronoun bound inside this check does not refer to rejected prose.
    local_body = REFERENCE.sub('', body) if local_check_references(body) else body
    if DEPENDENT.search(local_body) or DEPENDENT.search(label):
        return False
    from claim_scope import clauses
    statements=list(clauses(body))
    return bool(statements) and all(PREPARATION.match(part.text) or
        QUESTION.match(part.text) and part.text.rstrip().endswith('?') for part in statements)


PLAN_ACTION = re.compile(r'^\s*(?:run|prepare|define|outline|draft|compare|evaluate|design)\b',re.I)
PLAN_OBJECT = re.compile(r'\b(?:comparison|evaluation|qualification|checklist|test|checks|rubric)\b',re.I)
PLAN_VERBS = ('issue introduce switch ask score reject accept repeat include require keep record '
    'compare evaluate inspect measure trace return test verify check prepare define outline draft '
    'write collect obtain supply provide present request instruct prompt').split()
GERUNDS = {(verb[:-1] if verb.endswith('e') else verb)+'ing': verb for verb in PLAN_VERBS}
PLAN_STEP = re.compile(r'^\s*(?:'+'|'.join([*PLAN_VERBS, *GERUNDS])+r')\b',re.I)
REFERENCE = re.compile(r'\b(?:it|its|they|their|these|those)\b',re.I)
INTRODUCE = re.compile(r'\b(?:introduce|issue|supply|provide|present|define|prepare|write|record|'
    r'add|set|instruct|prompt)\s+(?:a|an|the)\s+([^.,;:!?]+)',re.I)
CRITERIA = re.compile(r'(?:acceptance|evaluation|success)\s+(?:criteria|rubric)',re.I)


def local_check_references(body):
    """Resolve only locally introduced check objects; ambiguous references fail."""
    from claim_scope import clauses, verification_governs
    introduced = False
    for clause in clauses(body):
        value = re.sub(r'\b(?:'+'|'.join(GERUNDS)+r')\b',
                       lambda m: GERUNDS[m[0].lower()], clause.text, flags=re.I)
        for reference in REFERENCE.finditer(value):
            prefix = value[:reference.start()]
            local = INTRODUCE.search(prefix)
            verification = re.search(r'\b(?:check|verify|test|assess|evaluate)\b', prefix, re.I)
            if not verification or not (introduced or local):
                return False
            if not verification_governs(value[verification.start():reference.start()]):
                return False
        introduced = introduced or bool(INTRODUCE.search(value))
    return True


def prospective_plan(unit):
    label,body=presentation(unit)
    if label and not body.strip():
        body=label+':'
        label=''
    if not body.rstrip().endswith(':') or DEPENDENT.search(label+' '+body):
        return False
    if re.search(r'\bto\s+(?:move|migrate|route|assign|delegate|enable|disable|deploy)\b',body,re.I):
        return False
    condition=re.match(r'^\s*(?:once|if|when|after)\b([^,]+),\s*(.+)',body,re.I|re.S)
    if condition:
        # Future verification is a prerequisite, never evidence it has passed.
        if not re.search(r'\b(?:is|are|has been|have been)\s+(?:verified|checked|confirmed|'
                         r'validated|established)\s*$',condition[1],re.I):
            return False
        body=condition[2]
    return bool(PLAN_ACTION.match(body) and PLAN_OBJECT.search(body) or
                re.match(r'^\s*before\b',body,re.I) and
                re.search(r'\b(?:prerequisites|requirements|checks)\b.*\bneed\s+inspection\s*:',body,re.I))


def attached_step(body):
    """Every proposition must describe a check, not just its opening verb."""
    from claim_scope import clauses
    if not local_check_references(body):
        return False
    for clause in clauses(body):
        value=clause.text.strip()
        if not PLAN_STEP.match(value):
            return False
        switch=re.match(r'^switch(?:ing)?\s+(?:to\s+)?',value,re.I)
        if switch:
            object_phrase=re.split(r'\b(?:to|from|for|with|under|before|after)\b',value[switch.end():],maxsplit=1,flags=re.I)[0]
            heads=re.findall(r'[\w-]+',object_phrase)
            if not heads or heads[-1].lower() not in ('topic','question','prompt','subject'):
                return False
    return True


@dataclass
class DependencyState:
    """A prospective procedure scopes attached steps, never establishes facts."""
    pending: bool = False
    plan_start: object = None
    criteria: bool = False

    def close_plan(self):
        self.plan_start=None
        self.criteria=False

    def consider(self,unit,valid,*,offset=0,taint=True):
        if not valid:
            self.pending=self.pending or taint
            self.close_plan()
            return False,None
        if not unit.strip():
            return True,self.plan_start
        if prospective_plan(unit):
            self.plan_start=offset
            self.criteria=False
            return True,self.plan_start
        if heading_unit(unit):
            heading=unit.strip().strip('# :')
            if CRITERIA.fullmatch(heading):
                self.criteria=True
            return True,self.plan_start
        label,body=presentation(unit)
        causal=bool(CAUSAL.search(label+' '+body))
        attached=False
        if self.plan_start is not None and not causal:
            from claim_scope import clauses, finite_predicate, DIRECTIVE
            heading=unit.strip().strip('# :')
            if CRITERIA.fullmatch(heading):
                self.criteria=True
                return True,self.plan_start
            if CRITERIA.fullmatch(label) and re.match(
                    r'^\s*[\w -]+\s+qualifies?\s+only\s+if\b', body, re.I):
                condition=re.split(r'\bonly\s+if\b', body, maxsplit=1, flags=re.I)[1]
                # Parse the condition as a proposed check; an appended new
                # assertion must not inherit the acceptance-criterion label.
                attached=len(list(clauses('Check whether '+condition))) == 1
            if ITEM.match(unit) or re.match(r'^\s*•\s+', unit):
                if self.criteria:
                    attached=not finite_predicate(body) and not DIRECTIVE.match(body) and not REFERENCE.search(label+' '+body)
                elif PLAN_STEP.match(body):
                    attached=attached_step(body) and not REFERENCE.search(label)
        if attached:
            return True,self.plan_start
        self.close_plan()
        return not self.pending or independent_after_rejection(unit),None


def drop_incomplete_promises(parts, decisions):
    """A filtered list cannot retain a promise of its original cardinality.

    Only remove the lead-in; never admit a child that failed either check.
    Keep original offsets and expose the removal in the delivery receipt.
    """
    from claim_evidence import COUNT_WORDS
    counted = re.compile(r'\b(?P<count>'+ '|'.join(COUNT_WORDS) + r'|\d+)'
        r'(?:\s+(?:acceptance|evaluation|success)\s+criteria\b|[- ]turn\b)', re.I)
    for index, (part, decision) in enumerate(zip(parts, decisions)):
        promise = counted.search(part)
        if not decision['accepted'] or not promise or not part.rstrip().endswith(':'):
            continue
        count = promise['count'].lower()
        expected = COUNT_WORDS.get(count, int(count) if count.isdigit() else 0)
        retained = 0
        for child, receipt in zip(parts[index+1:], decisions[index+1:]):
            if not child.strip():
                continue
            if not (ITEM.match(child) or re.match(r'^\s*(?:•\s+|Turn\s+\d+\b)', child, re.I)):
                break
            retained += receipt['accepted']
        if retained != expected:
            decision.update(accepted=False, reason='incomplete_counted_list')


def select(content, acceptable, *, pending=False, state=None):
    """Return original kept bytes, offset receipts and unresolved dependency."""
    state=state or DependencyState(pending=pending)
    # Separate structured paragraphs cannot silently inherit list attachment.
    state.close_plan()
    parts=list(units(content));decisions=[];offset=0
    for part in parts:
        valid=bool(acceptable(part))
        accepted,governor=state.consider(part,valid,offset=offset)
        dependent=valid and not accepted
        decisions.append(dict(start=offset,end=offset+len(part),accepted=accepted,
                              reason='unsupported_unit' if not valid else
                              'dependent_on_rejected_reasoning' if dependent else 'independent_or_supported',
                              prospective_governor_start=governor))
        offset+=len(part)
    drop_incomplete_promises(parts, decisions)
    return ''.join(part for part, receipt in zip(parts, decisions) if receipt['accepted']),decisions,state.pending

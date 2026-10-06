"""Bounded provenance for task results, shared by context and final delivery.

Receiving words or matching labels does not establish that work happened. User
scenario facts remain useful inside their scenario; saved report verification
establishes only that report's assignment and artifact, not all its conclusions.
"""
import copy
import hashlib
import re

from claim_scope import clauses, disposition, plain
from reported_records import source_bindings, topic_record, TASK_ID

RULES = '''Keep task-result provenance explicit for every referenced task, including
older tasks mentioned in a cached return. The result-provenance projection
distinguishes owner-stipulated scenario facts, received material/attributed claims,
and server-verified saved reports. A received payload is evidence of what was
received and claimed, not evidence of prior work completed. Task, source, lease,
artifact names and matching hashes alone do not prove execution or acceptance.
Preserve useful metadata and explain the next acceptance checks. Attribute an
unverified statement to its source instead of adopting it. Scenario facts apply
within the supplied scenario only; do not claim you independently verified them.
Superseded source records are historical; the latest owner correction governs.
Previous assistant prose supplies conversation continuity, never corroboration.
Verified report completion covers that saved assignment/artifact only; it does
not prove its recommendations were executed or establish current system health.
'''
SCENARIO = re.compile(r'\b(?:fictional|hypothetical|scenario|suppose|stipulate[ds]?)\b', re.I)
RECEIVED = re.compile(r'\b(?:cached|incoming|received|imported|payload|return(?:ed)?|artifact|'
                      r'report\s+(?:says|claims)|claims?\s+that)\b', re.I)
ATTRIBUTED = re.compile(r'\b(?:claims|claimed|says|said|states|stated|alleges|alleged|asserts|asserted|reports|reported)\s+(?:that\s+)?|\baccording to\b', re.I)
COMPLETED = re.compile(r'\b(?:completed|finished|succeeded|executed)\b|'
                       r'\b(?:is|was|has been|remains)\s+(?:now\s+)?(?:complete|done|successful)\b|'
                       r'\bmarked\b.{0,40}\bcomplete\b|'
                       r'\b(?:execution|completion)\s+(?:was|is|has been)\s+(?:verified|confirmed|proven)\b|'
                       r'\b(?:result|artifact|output)\s+(?:was|is|has been)\s+accepted\b', re.I)
IDENTITY = re.compile(r'\b(?:[A-Za-z][\w]*-\d+|webchat-[a-f0-9]{32})\b')
SELF_VERIFIED = re.compile(r'\b(?:I|we)\s+(?:have\s+)?(?:verified|confirmed|proved|established)\b', re.I)
VERIFICATION = re.compile(r'\b(?:verified|confirm(?:s|ed)?|prove[sd]?|proven|establish(?:es|ed)?)\b',re.I)


def effect_subjects(text,match,identities,*,nominal=False):
    """Task predicate subjects, not every task appearing in its object."""
    mentions=[m for m in IDENTITY.finditer(text) if m[0] in identities]
    before=[m for m in mentions if m.end()<=match.start()]
    preposed=re.match(r'^\s*(?:regarding|concerning|about|for|as for|with respect to)\b[^,]*,\s*',text,re.I)
    if preposed:before=[m for m in before if m.start()>=preposed.end()]
    if before:
        selected={before[0][0]};last=before[0]
        for other in before[1:]:
            # Only a coordinated subject shares the predicate. "Completed
            # the review of task B" leaves B as an object, not completed B.
            between=text[last.end():other.start()]
            if not re.fullmatch(r'\s*(?:,?\s*(?:and|or)\s+|,\s*)(?:(?:task|assignment)\s+)?',between,re.I):break
            selected.add(other[0]);last=other
        tail=text[last.end():match.start()]
        if re.fullmatch(r'\s*(?:(?:was|were|is|are|has|have|had|been|now|already|just|still|yet|\w+ly)\s+)*',tail,re.I):
            return selected
    # Nominal descriptions such as "work completed for task B" place the
    # result's task after its predicate. Keep the task-role binding local.
    after=[m for m in mentions if m.start()>=match.end()]
    if after:
        relation=text[match.end():after[0].start()]
        direct=re.fullmatch(r'\s*(?:(?:the\s+)?(?:task|assignment)\s+(?:ID\s+)?)?',relation,re.I)
        described=nominal and re.fullmatch(r'\s+(?:(?:work|report|review|result|artifact|output)\s+)?for\s+'
                                          r'(?:(?:the\s+)?(?:task|assignment)\s+(?:ID\s+)?)?',relation,re.I)
        suffix=text[after[0].end():]
        dependent=re.match(r"\s*(?:['’]s\b|(?:review|report|artifact|result|output|worker|reviewer|source|requirements?)\b)",suffix,re.I)
        if (direct or described) and not dependent:return {after[0][0]}
    return set()


def report_subject(part,match,alias):
    """A citation verifies its report, not surrounding recommendations."""
    position=part.text.find(alias)
    if position<0:return False
    prefix=(part.label+' '+part.text[:min(position,match.start())]).strip()
    head=re.fullmatch(r'(?:(?:the|a|this|that|our|my|saved|verified|historical|bounded|readiness|project|next-actions|completed)\s+)*'
                     r'(?:report|brief|assignment|artifact|result|output|task)\s*(?:\[report\s*)?',prefix,re.I)
    tail=part.text[position+len(alias):match.start()]
    return bool((head or not prefix) and re.fullmatch(r'[\]\s]*(?:(?:was|were|is|are|has|have|been|now|already|successfully)\s+)*',tail,re.I))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def predicate(match):
    value = match[0].lower()
    return ('execution' if value.startswith(('executed', 'execution')) else
            'result_acceptance' if value.startswith(('result', 'artifact', 'output')) else 'completion')


def nonasserted(part, match):
    if disposition(part, match.start(), match.end(), match[0]):
        return True
    prefix, suffix = part.text[:match.start()], part.text[match.end():]
    # A hypothetical/prerequisite is local to this proposition. A following
    # independent assertion is split and checked separately by claim_scope.
    if re.search(r'\b(?:if|unless|until|before|once|whether)\b', prefix, re.I):
        return True
    if re.search(r"\b(?:not|never|hasn['’]t|haven['’]t|wasn['’]t|weren['’]t)\s+(?:been\s+)?$",prefix,re.I):
        return True
    if re.search(
            r"\b(?:does not|doesn['’]t|cannot|can['’]t|not)\s+"
            r'(?:constitute\s+)?(?:evidence|proof)\s+(?:of\s+)?(?:prior\s+)?(?:work\s+)?$',
            prefix,re.I):
        return True
    if re.search(
            r"\b(?:does not|doesn['’]t|cannot|can['’]t)\s+"
            r'(?:constitute\s+)?(?:evidence|proof)\s+of\b|'
            r'\bnot (?:evidence|proof) of\b',
            part.text[:match.start()],re.I):
        return True
    if re.match(r'\s+(?:is|was|remains?)\s+(?:unverified|unknown|unproven)\b',suffix,re.I):
        return True
    return False


def projection(conversation):
    from conversation_focus import focus, CORRECTION
    record = focus(conversation) or {}
    excerpts = list(record.get('user_excerpts', []))
    latest = next((m for m in reversed(conversation.get('messages', [])) if m.get('role')=='user'), None)
    if latest and not any(e['message_id']==latest.get('id') for e in excerpts):
        text = latest.get('content', '')
        excerpts.append(dict(message_id=latest.get('id'),request_id=latest.get('request_id'),
                             content=text[:2400],truncated=len(text)>2400))
    record = dict(record,user_excerpts=excerpts)
    bindings = source_bindings(record)
    origin={k:excerpts[0].get(k) for k in ('message_id','request_id')} if excerpts else None
    previous=next((m.get('_reply_contract',{}).get('result_provenance')
                   for m in reversed(conversation.get('messages',[]))
                   if m.get('role')=='assistant' and
                   m.get('_reply_contract',{}).get('result_provenance',{}).get('origin')==origin),None)
    retained=copy.deepcopy((previous or {}).get('records',[]))
    chronological={m.get('id'):index for index,m in enumerate(conversation.get('messages',[])) if m.get('role')=='user'}
    for item in retained:bindings.setdefault(item['subject'],[])
    scenario = any(SCENARIO.search(e['content']) for e in excerpts)
    result = dict(version=1,origin=origin,topic=topic_record(record,bindings),records=retained,
                  prior_assistant_evidence=False,scope='Reported facts are not independently verified events.')
    for excerpt in excerpts:
        text = excerpt['content']; current = None; imported=set()
        corrected={i for i in bindings if re.search(r'\b'+re.escape(i)+r'\b',text)} if CORRECTION.match(text.strip()) else set()
        for old in result['records']:
            if old['subject'] in corrected and chronological.get(old['message_id'],-1)<chronological.get(excerpt['message_id'],-1):
                old['superseded_by']=excerpt['message_id']
        for part in clauses(text):
            subjects = [i for i in bindings if re.search(r'\b'+re.escape(i)+r'\b',part.text)]
            if subjects:current=subjects[0] if len(subjects)==1 else None
            elif current:subjects=[current]
            if not subjects:continue
            if RECEIVED.search(part.text) or ATTRIBUTED.search(part.text):imported.update(subjects)
            kind = ('received_claim' if set(subjects)&imported else
                    'owner_scenario' if scenario else 'owner_report')
            effects={subject:set() for subject in subjects}
            for match in COMPLETED.finditer(part.text):
                if nonasserted(part,match):continue
                claimed=effect_subjects(part.text,match,set(bindings))
                if (not claimed and len(subjects)==1 and
                        not any(i in part.text for i in bindings) and
                        re.match(r'^\s*(?:it|the task|this task|that task)\b',part.text,re.I)):
                    claimed=set(subjects)
                for subject in claimed & set(subjects):effects[subject].add(predicate(match))
            denied=any(nonasserted(part,m) and not part.question and
                       re.search(r"\b(?:not|never|no|cannot|can['’]t|hasn['’]t)\b",part.text[:m.start()],re.I)
                       for m in COMPLETED.finditer(part.text))
            if denied and kind=='owner_scenario':
                for old in result['records']:
                    if old['subject'] in subjects and (chronological.get(old['message_id'],-1),old['start'])<(chronological.get(excerpt['message_id'],-1),part.start):
                        old['superseded_by']=excerpt['message_id']
            for subject in subjects:
                result['records'].append(dict(subject=subject,kind=kind,predicates=sorted(effects[subject]),
                    message_id=excerpt['message_id'],request_id=excerpt['request_id'],
                    excerpt_sha256=digest(text),start=part.start,end=part.end,
                    text=text[part.start:part.end],sha256=digest(text[part.start:part.end]),
                    truncated=excerpt.get('truncated',False)))
    # These are prior server projections of user text, never prior generated
    # answers. Preserve their type across bounded focus trimming, not topics.
    unique={}
    for item in result['records']:
        key=(item['subject'],item['message_id'],item['start'],item['sha256'])
        prior=unique.get(key,{})
        if prior.get('superseded_by') and not item.get('superseded_by'):
            item=dict(item,superseded_by=prior['superseded_by'])
        unique[key]=item
    result['records']=list(unique.values())[-64:]
    result['omitted_records']=max(0,len(unique)-64)
    return result


def verified(root, bindings):
    """Revalidate server-selected saved reports; a model cannot supply bindings."""
    from project_reports import verified_report
    result=[]
    for binding in bindings:
        try:
            row,body=verified_report(root,binding['task_id'])
            if (row['result_sha256']!=binding['result_sha256'] or
                    row['report_contract']['contract_sha256']!=binding['contract_sha256'] or
                    digest(body)!=binding['artifact_sha256']):continue
            result.append(dict(subject=binding['task_id'],alias=binding['citation_alias'],
                kind='verified_saved_report',predicates=['execution','completion','result_acceptance'],
                result_sha256=row['result_sha256'],contract_sha256=binding['contract_sha256'],
                artifact_sha256=binding['artifact_sha256'],
                scope='Historical report assignment and saved bytes only; no other task, recommendation execution or present health.'))
        except (OSError,ValueError,KeyError,TypeError):
            continue
    return result


def deliver(root, content, source, report_bindings=()):
    records=list(source.get('records',[]))
    records += [dict(subject=b['task_id'],alias=b['citation_alias'],kind='selected_report_reference',predicates=[])
                for b in report_bindings]
    records += verified(root,report_bindings)
    known={r['subject'] for r in records}
    declared={m[1] for m in TASK_ID.finditer(plain(content))}
    declared.update(re.findall(r'\bwebchat-[a-f0-9]{32}\b',content))
    received={r['subject'] for r in records if r['kind']=='received_claim'}
    findings=[]; decisions=[]; current=None
    for part in clauses(content):
        alias_spans=[(m.start(),m.end()) for r in records if r.get('alias')
                     for m in re.finditer(re.escape(r['alias']),part.text)]
        explicit={m[0] for m in IDENTITY.finditer(part.text)
                  if m[0] in known|declared and not any(start<=m.start()<end for start,end in alias_spans)}
        aliases={r['subject'] for r in records if r.get('alias') and r['alias'] in part.text}
        subjects=explicit|aliases
        if subjects:current=next(iter(subjects)) if len(subjects)==1 else None
        elif RECEIVED.search(part.text):subjects=received if len(received)==1 else set()
        elif re.match(r'^\s*(?:it|its|this task|that task|the task)\b',part.text,re.I):
            subjects={current or source.get('topic')} - {None}
        else:subjects=set()
        for match in COMPLETED.finditer(part.text):
            claimed=effect_subjects(part.text,match,explicit,nominal=True) if explicit else set(subjects)
            if not claimed or nonasserted(part,match):continue
            prefix=part.text[:match.start()]
            # Attribution is a claim about what a source says, not an
            # endorsement. Explicit verification/endorsement cancels it.
            attributed=bool(ATTRIBUTED.search(prefix) and not SELF_VERIFIED.search(prefix) and
                            not re.search(r'\b(?:true|correct|proof|proves|confirms|establishes)\b',part.text,re.I))
            if attributed:continue
            required=predicate(match)
            for subject in sorted(claimed):
                available=[r for r in records if r['subject']==subject]
                support=[r for r in available if required in r['predicates'] and not r.get('superseded_by') and
                         (r['kind']=='verified_saved_report' and
                          (report_subject(part,match,r['subject']) or report_subject(part,match,r['alias'])) or
                          r['kind']=='owner_scenario' and not VERIFICATION.search(part.text))]
                decision=dict(start=part.start,end=part.end,sha256=digest(content[part.start:part.end]),
                    subject=subject,required_predicate=required,supported=bool(support),
                    available_evidence=available,reason='supported_within_source_scope' if support else 'reported_material_does_not_establish_result')
                decisions.append(decision)
                if not support and not any(f['start']==part.start for f in findings):findings.append(decision)
    if not findings:return content,dict(partial=False,claims=decisions,projection=source)
    result=[];offset=0;replaced=False
    for finding in findings:
        before=content[offset:finding['start']]
        before=re.sub(r'(?:,?\s*\b(?:and|or|but|yet|however|therefore|thus|so|then|because|since|which|that)\b\s*)+$','',before,flags=re.I)
        original=content[finding['start']:finding['end']]
        if re.search(
                r"\b(?:does not|doesn['’]t|cannot|can['’]t|not)\s+"
                r'(?:constitute\s+)?(?:evidence|proof)\s+of\b|'
                r'\bnot (?:evidence|proof) of\b|'
                r'\b(?:does not|cannot)\s+(?:verify|establish|prove|satisfy|complete)\b',
                original,re.I):
            result.append(before)
            result.append(original)
            offset=finding['end']
            continue
        replaced=True
        label=before.rstrip().rstrip('*_').endswith(':')
        if before.strip() and before[-1] not in '.!?\n:' and not label:before=before.rstrip()+'.\n'
        elif before.strip() and before[-1] in '.!?' and not before.endswith(('\n',' ')):
            before=before+' '
        result.append(before)
        marker=re.match(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)',original)
        if marker:result.append(marker[0])
        available=finding['available_evidence']
        if any(r['kind']=='verified_saved_report' for r in available):
            result.append('The saved report verifies its own assignment; other work described here still needs its own execution and result evidence.')
        elif available:
            result.append('The supplied material refers to '+finding['subject']+
                          '; this does not verify that task’s '+finding['required_predicate'].replace('_',' ')+'.')
        else:
            result.append('The '+finding['required_predicate'].replace('_',' ')+' of '+finding['subject']+
                          ' is unverified; no supporting task result was supplied.')
        offset=finding['end']
        result.append('\n')
    result.append(content[offset:])
    if not replaced:
        return content,dict(partial=False,claims=decisions,projection=source)
    return ''.join(result),dict(partial=True,claims=decisions,projection=source,
        evaluated_input_sha256=digest(content),scope='Bounded task-result provenance, not general semantic certification.')

"""Dispatch acknowledgements come from this turn's durable journal entries."""
import re


NO_DISPATCH = "I did not start, assign, or queue any work in this turn."
WORKERS = r"(?:Codex|Claude|Cursor|Gemini|MiniMax|the (?:system|dispatcher|workers?)|all (?:LLMs|workers))"
PLACEMENT_VERB = r"(?:put(?:ting)?|plac(?:e|ed|ing)|add(?:ed|ing)?|mov(?:e|ed|ing)|send(?:ing)?|sent|transfer(?:red|ring)?|submit(?:ted|ting)?)"
QUEUE_PLACEMENT = (PLACEMENT_VERB + r"\b[^.;!?\n]{0,70}\b(?:in(?:to)?|to)\s+"
                   r"(?:(?:a|an|the|my|your|our|this|that)\s+)?queue\b")
EFFECT = r"(?:start(?:ed|ing)?|creat(?:e|ed|ing)\b[^.!?\n]{0,60}\b(?:jobs?|tasks?)|assign(?:ed|ing)?|queue(?:d|ing)?|queuing|dispatch(?:ed|ing)?|launch(?:ed|ing)?|schedul(?:e|ed|ing)|delegat(?:e|ed|ing)|add(?:ed|ing)? work|put .{0,40} to work|kick(?:ed|ing)? off|" + QUEUE_PLACEMENT + r")"
CLAUSE_START = r"(?:^|[.;!?\n–—]\s*|\b(?:and|then|but|yet)\s+)"
BARE_EFFECT = CLAUSE_START + r"(?:queued|assigned|started|dispatched|launched|scheduled)\b"
# Project IDs and paths are not speaking actors. A heading boundary also
# cannot make an actor in that heading the subject of a later assignment.
ACTOR = r"(?<![\w./-])(?:[_*]{1,2})?(?:I|we|Bob|" + WORKERS + r")(?:[_*]{1,2})?(?![\w/-])"
# A speaking subject must govern the effect predicate. An arbitrary later noun
# ("we keep discussing memory and queue state") is not an action by that subject.
ACTOR_PREDICATE = (r"(?:['’](?:ve|ll|d|m|re|s))?\s*(?:[*_]*\s*:\s*[*_]*\s*)?"
                   r"(?:(?:has|have|had|is|are|was|were|will|would|can|could|may|might|must|should|did|do|"
                   r"just|now|already|also|still|finally|[a-z]+ly|been|being|get|got)\s+){0,6}")
CAUSATIVE = r'(?:(?:ask(?:ed)?|tell|told|instruct(?:ed)?|use[ds]?)\s+(?:Bob|'+WORKERS+r')\s+to\s+)'
ACTOR_EFFECT = ACTOR + ACTOR_PREDICATE + r'(?:'+CAUSATIVE+r')?' + EFFECT + r"\b"
# An undertaking governs its predicate. A purpose infinitive later in a
# proposed comparison ("run a test to ensure ...") is not that undertaking.
# Preserve coordinated promises rather than matching only the first verb.
UNDERTAKING = r"(?:make sure|ensure|utiliz\w*|prioritiz\w*|keep [^.!?\n]{0,35}busy|maximize|adding work)"
FUTURE_ACTOR = r"\b(?:I['’]ll|I will|we['’]ll|we will|the system (?:will|is))\s+"
COMMITMENT = (FUTURE_ACTOR +
              r"(?:(?:now|also|always|actively|definitely|certainly)\s+){0,3}"
              r"(?:" + UNDERTAKING + r"|"
              r"(?:(?!\b(?:to|if|when|unless)\b)[^.;!?\n]){1,100}"
              r"\b(?:and|then|but|yet)\s+(?:will\s+)?"
              r"(?:(?:now|also|always|actively|definitely|certainly)\s+){0,3}" + UNDERTAKING + r")|"
              + FUTURE_ACTOR + r"[^.;!?\n]{0,160}\b(?:and|then|but|yet)\s+will\s+"
              r"(?:(?:now|also|always|actively|definitely|certainly)\s+){0,3}" + UNDERTAKING)
CLAIM = re.compile(
    ACTOR_EFFECT + r"|"
    + BARE_EFFECT + r"|"
    r"\b(?:work|jobs?|tasks?|reviews?|audits?|tests?)\b[^:.!?\n]{0,80}\b(?:has|have|is|are|was|were|being|been)\b"
    r"[^.!?\n]{0,30}\b" + EFFECT + r"\b|"
    r"\b(?:work|jobs?|tasks?|reviews?|audits?|tests?)\b[*_]*\s*:\s*[*_]*\s*"
    r"(?:(?:has|have|is|are|was|were|been|now|just|already)\s+){0,4}" + EFFECT + r"\b|"
    + COMMITMENT + r"|"
    r"\b" + WORKERS + r"\b[^.;!?\n]{0,45}\b(?:is|are) (?:now )?(?:working|running|busy|on it)\b|"
    r"\b(?:I['’]ve|I have|we['’]ve|we have) (?:put|got|set)\b[^.!?\n]{0,60}\b(?:working|busy|work|task|job)\b",
    re.I,
)
JOB_ID = re.compile(r"\bwebchat-[a-f0-9]{32}\b")
# In an explanation, generic jobs are examples. Owner references and named
# jobs still make concrete claims; they need the same real receipts as actions.
# A determiner belongs to its noun phrase, not to any later job in a clause.
# "proven that the job..." and "these conditions indicate the work..." are
# reports about evidence, not ownership of a task. Do not cross another
# determiner, a predicate, or a clause boundary when looking for the subject.
TARGET_MODIFIER = (r"(?!(?:a|an|the|your|our|my|this|that|these|those|is|are|was|were|has|have|had|"
                   r"does|do|did|can|could|will|would|means|mean|shows?|proves?|indicates?|establishes?|"
                   r"and|or|but|which|when|once|if|until|job|jobs|task|tasks|work|council|"
                   r"queue|state)\b)[\w'-]+\s+")
REFERENCE_TARGET = (r"\b(?:your|our|my)\s+(?:" + TARGET_MODIFIER + r"){0,4}(?:jobs?|tasks?|work|council)\b|"
                    r"\b(?:this|that)\s+(?:" + TARGET_MODIFIER + r"){0,4}(?:job|task|work|council)\b|"
                    r"\b(?:these|those)\s+(?:" + TARGET_MODIFIER + r"){0,4}(?:jobs|tasks)\b|"
                    # A state label alone is not a job name. Ownership still
                    # binds "your queued task"; another modifier identifies
                    # named work such as "the scheduled parser repair job".
                    r"\bthe\s+(?!(?:(?:queued|running|started|scheduled|assigned|waiting)\s+){1,4}(?:job|task)\b)"
                    r"(?:" + TARGET_MODIFIER + r"){1,4}(?:job|task)\b")
ASSERTION_AUX = r"(?:is|are|was|were|has|have|had|be|been|being|will|would|shall|should|can|could|may|might|must|get|gets|got)"
ASSERTION_ADVERB = r"(?:now|just|already|still|also|then|[a-z]+ly)"
CONTINUATION_JOIN = r'(?:\b(?:and|then|but|yet)|[;–—])\s+'
COORDINATED_EFFECT = re.compile(
    CONTINUATION_JOIN +
    r'(?:(?:I|we|he|she|it|they)\s+)?'
    r'(?:(?:' + ASSERTION_AUX + r'|' + ASSERTION_ADVERB + r')\s+){0,4}' + EFFECT + r'\b', re.I)
QUEUE_STATE = (r"in\s+(?:(?:a|an|the|my|your|our|this|that|[\w]+['’]s)\s+)?"
               r"(?:" + TARGET_MODIFIER + r"){0,3}queue\b")
# Recognize a predicate associated with the target, not any effect word later
# in its sentence. A new imperative or noun phrase does not inherit ownership:
# "review your tasks, note that a queued receipt..." is a guide, not dispatch.
# Keep modifiers and shared-subject coordination such as "the task you requested
# was inspected and queued", including a closed parenthetical or relative.
TARGET_PREDICATE = (
    r"[*_]*\s*(?:[,(:]\s*[^,;.!?\n]{1,60}[,)]+\s*)?"
    r"(?:(?:,\s*)?(?:that|which)\s+)?"
    r"(?:(?:I|you|we|they|he|she)\s+[a-z]+\s+)?"
    r"(?::\s*)?"
    # Negation normalization removes one predicate only. Its positive
    # continuation still belongs to this subject, including after a comma.
    r"(?:has no established action\s*,?\s*(?:and|but|yet|then)\s+|"
    r"(?:" + ASSERTION_AUX + r")\s+[a-z]+\s+(?:and|then|but)\s+|"
    r"(?:" + ASSERTION_AUX + r"|" + ASSERTION_ADVERB + r")\s+|"
    r"[a-z]+(?:ed|en)\s+(?:" + ASSERTION_ADVERB + r"\s+){0,2}(?:and|then|but)\s+|"
    r"(?:and|then|but)\s+){0,10}"
    r"(?:" + EFFECT + r"|" + QUEUE_STATE + r")\b")
REFERENCE_EFFECT = re.compile(
    BARE_EFFECT + r"|"
    r"(?:" + REFERENCE_TARGET + r")" + TARGET_PREDICATE + r"|"
    r"\b(?:the|a) (?:job|task) (?:is|was|has|had)\s+(?:(?:just|now|already|been)\s+)*" + EFFECT + r"\b|"
    # State-only modifiers are not job names, but a deictic assertion about
    # that subject still claims a current effect rather than defining a term.
    r"\b(?:the|a)\s+(?:(?:queued|running|started|scheduled|assigned|waiting)\s+){1,4}(?:job|task)\b"
    r"(?=[^.;!?\n]{0,120}\b(?:now|just|already|currently|today|here)\b)" + TARGET_PREDICATE, re.I)
DIRECT_CLAIM = re.compile(
    ACTOR_EFFECT + r"|"
    r"\b" + WORKERS + r"\b[^.;!?\n]{0,45}\b(?:is|are) (?:now )?(?:working|running|busy|on it)\b|"
    r"\b(?:I['’]ve|I have|we['’]ve|we have) (?:put|got|set)\b[^.!?\n]{0,60}\b(?:working|busy|work|task|job)\b",
    re.I,
)


def verbal_effects(prose):
    """Disambiguate instructions, suggestions, and determined queue nouns.

    Used only for actor claims. A concrete job's queue state remains a claim
    under REFERENCE_EFFECT. Placement into a queue is an effect, too. Mask
    only immediate nonassertive terms and preserve bounded-scan offsets.
    """
    def remaining_sentence(match):
        end = re.search(r'[.!?\n]', prose[match.end():])
        return prose[match.end():match.end() + end.start()] if end else prose[match.end():]

    def instruction_actor(match):
        # An imperative object is not the subject of a later state adjective.
        # Retain it when a pronoun subsequently asserts that actor's effect.
        tail = remaining_sentence(match)
        if re.search(r'\b(?:he|she|it|they)\s+(?:(?:' + ASSERTION_AUX + r'|' + ASSERTION_ADVERB +
                     r')\s+){0,4}' + EFFECT + r'\b', tail, re.I):
            return match[0]
        return match[0][:match.start('actor') - match.start()] + ' ' * len(match['actor'])

    # A conjunction may continue a shared-subject promise rather than begin
    # an owner-directed instruction; only punctuation or the start qualifies.
    prose = re.sub(r'(?:^|[.;!?\n–—]\s*)(?P<instruction>(?:please\s+)?(?:ask|tell|use|try)\s+)'
                   r'(?P<actor>(?:Web\s+)?Bob|' + WORKERS + r')\b',
                   instruction_actor, prose, flags=re.I)

    def suggested_predicate(match):
        # Keep a positive shared-subject continuation, including one beyond
        # the bounded actor scan. Normalize only the immediate suggestion.
        if COORDINATED_EFFECT.search(remaining_sentence(match)):
            return match[0]
        return match['prefix'] + ' ' * len(match['predicate'])

    prose = re.sub(r"\b(?P<prefix>(?:I|we)\s+(?:suggest|recommend|propose)\s+)"
                   r"(?P<predicate>starting|queueing|queuing|assigning|dispatching|launching|scheduling|delegating)\b",
                   suggested_predicate, prose, flags=re.I)
    prose = re.sub(r"\b(?P<prefix>(?:let['’]s|let us|helps?\s+you)\s+get\s+)"
                   r"(?P<predicate>started)\b", suggested_predicate, prose, flags=re.I)
    placements = {m.end() - len('queue') for m in re.finditer(QUEUE_PLACEMENT, prose, re.I)}
    return re.sub(r"(\b(?:a|an|the|my|your|our|this|that|in|into|on|from|of|[\w]+['’]s)\s+)queue\b",
                  lambda m: m[0] if m.end() - len('queue') in placements else m[1] + ' ' * len('queue'),
                  prose, flags=re.I)


def unasserted_prose(prose):
    """Mask a negative predicate, never a later positive effect assertion.

    This text is used only for claim detection. The delivered answer retains
    its original wording. Contrast, coordination and punctuation end the scope;
    a disclaimer cannot shelter an appended action or receipt.
    """
    # Access to assigned inputs describes reach; 'assigned' is an adjective,
    # not an act of assignment by the earlier named provider. Preserve every
    # later predicate and receipt, including shared-subject actual effects.
    prose = re.sub(r'\b(?P<prefix>(?:for|in|within|inside|from|through|access(?:es|ing)?(?:\s+to)?|'
                   r'read(?:s|ing)?|inspect(?:s|ing)?)\s+)assigned'
                   r'(?=\s+(?:worktrees?|repositories|repos?|files?|inputs?|evidence)\b)',
                   lambda m: m['prefix']+' '*len('assigned'),prose,flags=re.I)
    # An exact zero-count noun phrase cannot acknowledge a positive effect.
    # Replace only that phrase; preserve a following actor, ID or predicate.
    prose = re.sub(r'\b(?:0|zero|no)\s+(?:(?:live|active|claimed|queued|running)\s+){0,3}'
                   r'(?:workers?|jobs?|tasks?)\b(?:\(s\))?(?:\s+(?:running|queued|claimed))?',
                   'no recorded items',prose,flags=re.I)
    # Match one immediate predicate, never a tail of arbitrary words. In
    # particular, EFFECT contains object-spanning forms such as create...job
    # that must not be used to erase the scope of a negation.
    verb = (r'(?:start(?:ed|ing)?|creat(?:e|ed|ing)|assign(?:ed|ing)?|queue(?:d|ing)?|queuing|'
            r'dispatch(?:ed|ing)?|launch(?:ed|ing)?|schedul(?:e|ed|ing)|delegat(?:e|ed|ing)|'
            + PLACEMENT_VERB + r'|kick(?:ed|ing)? off|running|working|in progress|picked up)\b')
    denial = (r"\b(?:(?:does|do|did|would|could)(?: not|n['’]t)|cannot|can['’]t)\s+"
              r"(?:prove|establish|show|confirm|mean|demonstrate|indicate|assume)\b|"
              r"\bno (?:evidence|proof|record)\s+(?:shows?|proves?|establishes?|confirms?|that)\b|"
              r"\bnot that\b")
    subject = (r'(?:(?:the|a|your|our|my|this|that)\s+)?'
               r'(?:(?:background|bounded|pending|requested|assigned)\s+){0,2}(?:work|jobs?|tasks?|tests?)|'
               r'I|we|Bob|' + WORKERS)
    proposition = (r'(?P<prefix>(?:' + denial + r')\s+(?:that\s+)?(?:' + subject + r')\s+)'
                   r'(?:(?:has|have|had|is|are|was|were|been|being|already|now|currently|just)\s+){0,4}' + verb)
    def denied_proposition(match):
        end=re.search(r'[.!?\n]',prose[match.end():])
        tail=prose[match.end():match.end()+end.start()] if end else prose[match.end():]
        # Keep the subject when a later shared-subject affirmative needs it.
        # Otherwise this immediate denied proposition is explanatory data;
        # its complementizer ("not that work...") is not a deictic owner.
        affirmative=re.compile(CONTINUATION_JOIN +
                               r'(?:(?:it|they)\s+)?(?:(?:'+ASSERTION_AUX+r'|'+ASSERTION_ADVERB+r')\s+){0,4}'+verb,re.I)
        if affirmative.search(tail):
            return match['prefix']+'has no established action'
        return 'unproven assertion'
    prose = re.sub(proposition, denied_proposition, prose, flags=re.I)
    # Auxiliary negation belongs to this predicate only, not the sentence.
    prose = re.sub(r"\b(?:(?:is|are|was|were|has|have|had|will|would|can|could|may|might|must|should)"
                   r"(?: not|n['’]t)|cannot|won['’]t|can['’]t|shan['’]t)\s+"
                   r"(?:(?:yet|ever|actually|already|currently|be|have|been|being)\s+){0,3}" + verb,
                   'has no established action', prose, flags=re.I)
    # A future offer explicitly contingent on the owner's confirmation is not
    # a current effect. Mask just its predicate, keeping any following claim.
    prose = re.sub(r"\b(?:just\s+)?say\s+(?:go|yes)\s+and\s+I(?:['’]ll| will)\s+" + verb,
                   'an offer awaiting confirmation', prose, flags=re.I)
    # Starting an explanation from an abstract premise is not starting a job.
    # Normalize only the immediate reasoning predicate, retaining actors and
    # every other clause. A shared-subject effect later in this sentence keeps
    # the original predicate detectable even beyond the bounded actor scan.
    abstract = r'(?:limits?|constraints?|facts?|evidence|premises?|assumptions?|requirements?|priorities|priority|criteria|options?|reasoning)'
    phrase_end = r'(?=$|\s*[,;.!?\n]|\s+(?:and|then|but|yet|rather|because|instead|before|after)\b)'
    reasoning = re.compile(r"\b(?:I|we)\s+(?:(?:have|had|first|initially)\s+)?start(?:ed|ing)?\s+"
                           r"(?:(?:with|from)\s+(?:(?:the|a|an|your|our|this|that)\s+)?"
                           r"(?:(?:hard|time|cost|given|stated|supplied|original|initial)\s+){0,3}" + abstract + r"\b|"
                           r"by\s+(?:considering|comparing|explaining|reasoning about)\b[^.;!?\n]{0,60}\b" + abstract + r"\b)" + phrase_end, re.I)
    def reasoning_predicate(match):
        end = re.search(r'[.!?\n]', prose[match.end():])
        tail = prose[match.end():match.end() + end.start()] if end else prose[match.end():]
        if COORDINATED_EFFECT.search(tail):
            return match[0]
        return re.sub(r'\bstart(?:ed|ing)?\b', 'reasoned', match[0], count=1, flags=re.I)

    return reasoning.sub(reasoning_predicate, prose)


GENERIC_STATE = re.compile(
    r'\b(?:the|a) (?P<subject>job|task)\s+(?:is|was|has been|had been)\s+'
    r'(?:(?:marked|listed|shown|described|labelled|labeled)\s+(?:as\s+)?)?'
    r'(?P<state>queued|running|started|assigned|scheduled)\b', re.I)
CURRENT_EFFECT = re.compile(r'\b(?:now|just|already|currently|today|here|this machine)\b', re.I)


def reference_context(text, conversation):
    """One adjacent user-supplied reference may support an explicit follow-up.

    Never inherit state from assistant prose, skip across a new topic, or use
    old facts to undo a correction. This supplies discussion data only.
    """
    from answer_intent import conceptual
    from conversation_focus import CORRECTION
    if (not re.search(r'\b(?:same|supplied|provided) (?:evidence|facts|data)\b', text, re.I)
            or GENERIC_STATE.search(text) or CORRECTION.match(text.strip())
            or re.search(r'\b(?:jobs?|tasks?|work)\s+(?:is|are|was|were|has|have|had)\b|'
                         r'\b(?:no longer|correction|actually|instead)\b', text, re.I)):
        return text
    users = [m.get('content', '') for m in (conversation or {}).get('messages', []) if m.get('role') == 'user']
    if users and users[-1] == text:
        users.pop()
    if users and conceptual(users[-1]) and GENERIC_STATE.search(unasserted_prose(users[-1])):
        return users[-1] + '\n' + text
    return text


def dispatch_prose(text, *, reference=''):
    # Code examples are not action acknowledgements. Prose still needs the
    # same effect checks; quotation marks alone cannot shelter a receipt.
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    prose = unasserted_prose(prose)
    # An instruction to ask an actor for work is not that actor performing it.
    # Normalize only the infinitive predicate, preserving every later clause.
    infinitive = (r'(?:start|create|assign|queue|dispatch|launch|schedule|delegate|'
                  r'submit|send|put|kick off)\b')
    prose = re.sub(r'(?:^|(?<=[.;!?\n])\s*)(?:please\s+)?(?:ask|tell|instruct)\s+'
                   r'(?:Bob|' + WORKERS + r')\s+to\s+' + infinitive,
                   'request an action', prose, flags=re.I)
    # Mask only a conditional's state predicate, in either order. An owned or
    # named task can appear in a hypothetical without proving its live state.
    # Never erase its following clauses: they may assert a real owned/named
    # effect even without an explicit actor or job ID.
    predicate = r'(?:a (?:job|task)|jobs|tasks)\s+(?:is|are|has|have)\s+(?:been\s+)?(?:queued|running|started|assigned|scheduled)\b'
    conditional = r'(?:when|if|until|once|how)'
    subject = (r'(?:(?:a|an|the|your|our|my|this|that)\s+(?:' + TARGET_MODIFIER + r'){0,4}'
               r'(?:jobs?|tasks?|work)|jobs|tasks)')
    condition_state = (subject + r'\s+(?:is|are)\s+'
                       r'(?:queued|running|started|assigned|scheduled)\b')
    # 'how your task was queued' and 'I confirmed when...' report an effect.
    # Only a clause-leading present condition may normalize an owned subject.
    prose = re.sub(r'(?:^|(?<=[.;!?\n])\s*)(?:when|if|until|once)\s+' + condition_state,
                   'the described condition', prose, flags=re.I)
    prose = re.sub(r'\b' + conditional + r'\s+' + predicate,
                   'the described condition', prose, flags=re.I)
    prose = re.sub(r'(?:^|(?<=[.!?])\s+)' + predicate + r'(?=\s+' + conditional + r'\b)',
                   'The described state', prose, flags=re.I)
    # A conditional offer is not a claim that work was done.
    # Remove only the actor/modal and its immediate verb; never swallow the
    # rest of an offer or denial, which may contain a separate effect claim.
    prose = re.sub(r"\bI (?:did(?: not|n['’]t)|have(?: not|n['’]t))"
                   r"\s+(?:been\s+)?[a-z]+\b", 'unasserted predicate', prose, flags=re.I)
    # A capability or proposal is not a receipt or an unconditional promise.
    # Only its base-form predicates inherit this modal. Past/finite effects in
    # a continuation remain independently visible, including shared subjects.
    base_action=r'(?:start|create|assign|queue|dispatch|launch|schedule|delegate|add|put|send|transfer|submit|review|inspect|ask|tell|instruct|use)'
    modal=re.compile(r'(?P<actor>'+ACTOR+r')\s+(?:can|could|should|may|might)\s+'
                     r'(?:(?:not|[a-z]+ly)\s+){0,3}(?P<verb>'+base_action+r')\b',re.I)
    def possible_actions(match):
        tail=match['tail']
        def shared(candidate):
            prefix=tail[:candidate.start()]
            # An intervening actor, finite action or contrast ends the modal's
            # scope. Never mask an actual effect asserted after the proposal.
            new_predicate=ACTOR+ACTOR_PREDICATE+r'(?:[a-z]+ed|read|saw|took|found|sent|put|'+EFFECT+r')\b'
            if (re.search(new_predicate,prefix,re.I) or
                    re.search(r'\b(?:he|she|it|they|but|yet|then|will|have|has|had|did|queued|assigned|delegated|sent)\b',prefix,re.I)):
                return candidate[0]
            return candidate['join']+'a possible action'
        tail=re.sub(r'(?P<join>\band\s+)(?:'+base_action+r')\b',shared,tail,flags=re.I)
        return match['actor']+' describes a possible action'+tail
    modal_clause=re.compile(modal.pattern+r'(?P<tail>[^.;!?\n]*)',re.I)
    prose=modal_clause.sub(possible_actions,prose)
    # Replace only the explicitly excluded verb. Separate positive claims
    # remain visible to the guard, including after a semicolon or conjunction.
    prose = re.sub(r'\bwithout\s+(?:starting|creating|assigning|queueing|queuing|dispatching|'
                   r'launching|scheduling|delegating|adding|putting|kicking off)\b',
                   'without performing an action', prose, flags=re.I)
    if reference:
        # In a definition, generic subjects describe the term, not a live job.
        # Preserve owner/named-job, actor and deictic claims for the guard.
        def definition_subjects(match):
            part = match[0]
            # 'that' introducing an explanation is not a deictic task owner.
            # REFERENCE_TARGET checks actual ownership; current-effect words
            # belong to the body, not 'just means' describing the label.
            body = match['body']
            if (DIRECT_CLAIM.search(verbal_effects(part)) or JOB_ID.search(part) or re.search(REFERENCE_TARGET, part, re.I)
                    or CURRENT_EFFECT.search(body)):
                return part
            return re.sub(r'\b(?:the|a) (?:job|task)\b', 'the described state', part, flags=re.I)
        meaning = r'(?:(?:only|simply|just)\s+)?(?:means|indicates|signifies|confirms|shows)'
        prose = re.sub(r'(?:^|(?<=[.;!?])\s+)(?:(?:a|the)\s+)?(?:queued|running|assigned|scheduled)'
                       r'(?:\s+(?:receipt|status|state|label))?\s+' + meaning + r'\b(?P<body>[^.;!?\n]*)',
                       definition_subjects, prose, flags=re.I)
        # Exempt only a definition's subject, never the rest of its sentence.
        # "Queued means accepted; I started it" must still fail the guard.
        # A state adjective before a generic noun is not an omitted-actor
        # receipt either. Leave the noun's predicate visible: "Queued work is
        # now running" still asserts progress and must fail the other guard.
        nominal = (r'(?:work|jobs?|tasks?|receipts?|status|states?|labels?)\s+'
                   r'(?:is|are|was|were|has|have|had|does|do|can|cannot)\b')
        def nominal_subject(match):
            end = re.search(r'[.;!?\n]', prose[match.end():])
            tail = prose[match.end():match.end() + end.start()] if end else prose[match.end():]
            # Keep the nominal subject's own positive action predicate, even
            # for plurals or past tense. Later explanatory verbs are not its
            # predicate: queued work can be waiting until a worker starts it.
            subject = re.match(r'\s+(?:work|jobs?|tasks?)\b', tail, re.I)
            if subject and re.match(TARGET_PREDICATE, tail[subject.end():], re.I):
                return match[0]
            return match[1] + 'The described'
        negative_meaning = (r"(?:does|do)(?: not|n['’]t)\s+(?:mean|imply|prove|show|confirm|establish)\b|"
                            r"is not\s+(?:the same as|equivalent to|proof(?: of)?)\b")
        prose = re.sub(r'(?im)(' + CLAUSE_START + r')(?:queued|assigned|started|dispatched|launched|scheduled)'
                       r'(?=\s+(?:' + meaning + r'\b|' + negative_meaning + r'|is a state\b|' + nominal + r'))',
                       nominal_subject, prose)
        # A supplied generic state may be discussed verbatim. No actor, owner,
        # job ID, or named task can acquire an action receipt through this path.
        supplied = {(m['subject'].lower(), m['state'].lower())
                    for m in GENERIC_STATE.finditer(dispatch_prose(reference))}
        def supplied_state(match):
            # A source paraphrase does not license a new current-effect claim.
            start = max(prose.rfind(c, 0, match.start()) for c in '.;!?\n') + 1
            ends = [prose.find(c, match.end()) for c in '.;!?\n']
            end = min((n for n in ends if n >= 0), default=len(prose))
            if CURRENT_EFFECT.search(prose[start:end]):
                return match[0]
            key = (match['subject'].lower(), match['state'].lower())
            return 'the supplied state' if key in supplied else match[0]
        prose = GENERIC_STATE.sub(supplied_state, prose)
    return prose


def claims_dispatch(text, *, reference=''):
    # Direct actors and concrete IDs never receive a reference exemption.
    original = dispatch_prose(text)
    # Do not use the passive proximity heuristic for a conceptual answer: a
    # definition can describe assignment without asserting a particular job.
    claim = REFERENCE_EFFECT if reference else CLAIM
    actor_prose=verbal_effects(original)
    # A finite continuation retains its subject across a long subordinate
    # phrase. Base-form actions still governed by can/could are proposals.
    continuation=re.compile(r'\b(?:and|then|but|yet)\s+(?:will|have|has|had|did)\s+'+
                            ACTOR_PREDICATE+r'(?:'+CAUSATIVE+r')?'+EFFECT+r'\b',re.I)
    causative_continuation=re.compile(r'\b(?:and|then|but|yet)\s+'+CAUSATIVE+EFFECT+r'\b',re.I)
    pronoun=re.compile(r'(?:[;.!?]\s*|\b(?:and|then|but|yet)\s+)(?:he|she|it|they)\b'+ACTOR_PREDICATE+EFFECT+r'\b',re.I)
    inherited=bool(re.search(ACTOR,actor_prose,re.I) and (continuation.search(actor_prose) or pronoun.search(actor_prose)))
    completed_continuation=re.compile(r'\b(?:and|then|but|yet)\s+(?:started|assigned|queued|dispatched|launched|scheduled|delegated|'+QUEUE_PLACEMENT+r')\b',re.I)
    inherited=inherited or bool(re.search(ACTOR,actor_prose,re.I) and completed_continuation.search(actor_prose))
    inherited=inherited or bool(re.search(r"\b(?:I|we)(?:['’]ll| will| have| did)\b",actor_prose,re.I) and causative_continuation.search(actor_prose))
    checked=dispatch_prose(text,reference=reference)
    # The normalized denied subject may be shared by a later progress claim.
    # The denial itself stays nonassertive; only its affirmative continuation
    # is counted, with no exemption for reference prose.
    progress_continuation=re.compile(CONTINUATION_JOIN + r'(?:(?:it|they)\s+)?'
                                    r'(?:(?:is|are|was|were|has|have|had|been|being|be|will|must|'+ASSERTION_ADVERB+r')\s+){0,4}'
                                    r'(?:running|working|in progress|picked up)\b',re.I)
    denied_progress=any(progress_continuation.search(match['tail']) for match in re.finditer(
        r'has no established action(?P<tail>[^.!?\n]*)',original,re.I))
    return bool(DIRECT_CLAIM.search(actor_prose) or JOB_ID.search(original) or inherited
                or denied_progress
                or claim.search(checked if reference else verbal_effects(checked)))


def receipt_errors(answer, records, conversation_id, request_id, turn_started_at):
    """Reject invented, old, foreign, uncited, or omitted dispatch receipts."""
    identifiers = answer.get("task_ids") or ([answer["task_id"]] if answer.get("task_id") else [])
    errors = []
    for identifier in identifiers:
        row = records.get(identifier)
        if not row:
            errors.append("job does not exist: " + identifier)
            continue
        expected = request_id + ":" + str(row["group_index"]) if row.get("group_id") else request_id
        if row.get("conversation_id") != conversation_id or row.get("request_id") != expected:
            errors.append("job belongs to another turn: " + identifier)
        if row.get("created_at", 0) < turn_started_at:
            errors.append("job predates this turn: " + identifier)
        if identifier not in answer.get("content", ""):
            errors.append("receipt does not cite job: " + identifier)
    if len(identifiers) != len(set(identifiers)):
        errors.append("duplicate receipt ID")
    if set(JOB_ID.findall(answer.get("content", ""))) - set(identifiers):
        errors.append("reply cites a job outside its dispatch receipts")
    expected_ids = {row["id"] for row in records.values()
                    if row.get("conversation_id") == conversation_id and
                    (row.get("request_id") == request_id or
                     row.get("request_id", "").startswith(request_id + ":"))}
    if expected_ids != set(identifiers):
        errors.append("reply does not account for every job created in this turn")
    return errors


def verify_saved_receipt(root, conversation, message):
    import task_queue
    user = next(m for m in conversation["messages"] if m.get("role") == "user"
                and m.get("request_id") == message["request_id"])
    errors = receipt_errors(message, task_queue.tasks(root), conversation["id"],
                            message["request_id"], user["created_at"])
    if errors:
        raise ValueError("Cannot acknowledge dispatch: " + "; ".join(errors))

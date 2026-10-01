"""Answer requests are not worker assignments merely because they use a verb.

Explicit worker selection and local-file operations are resolved by the caller
first. This module owns only the answer/deliverable distinction; it never grants
permission, selects a project, or acknowledges an effect.
"""
import re


ANSWER = re.compile(r'^(?:write|draft|compose|summari[sz]e|compare|analy[sz]e|explain|'
                    r'calculate|evaluate|grade|score|research|review|plan|'
                    r'(?:give|show|offer|provide) me|suggest|brainstorm)\b', re.I)
REVISION = re.compile(r'^(?:make|keep|rewrite|revise|shorten|expand|rephrase)\b.{0,70}\b'
                      r'(?:reply|replies|answer|explanation|paragraph|poem|story|draft|wording|summary)\b', re.I)
TEXT_DELIVERABLE = re.compile(r'^(?:make|create|prepare|put together|produce|build)\s+(?:(?:me|us)\s+)?'
                              r'(?:(?:a|an|the|some)\s+)?(?:[a-z]+[ -]){0,3}'
                              r'(?:checklist|outline|list|table|draft|message|note|paragraph|poem|story|'
                              r'lyrics|email|explanation|summary|comparison|plan|invitation|guide)\b'
                              r'(?!\s+(?:app|tool|script|service|file)\b)', re.I)
ARTIFACT_OPERATION = re.compile(r'\b(?:create|open|submit|publish|commit|merge)\b.{0,35}\b'
                                r'(?:pull request|PR|branch|commit)\b', re.I)
RETRIEVAL_TARGET = re.compile(r'\b(?:PR|pull request|issue)\s*#?\d+\b|'
                              r'\bcommit\s+[a-f0-9]{7,40}\b|https?://\S+', re.I)
CONCEPT = re.compile(r'\b(?:difference between|what .{0,25}means?|meaning of|'
                     r'using only (?:this|the) (?:supplied|provided)|'
                     r'(?:supplied|provided) (?:evidence|facts|note|code)|'
                     r'explain (?:this|the) (?:quote|term|concept))\b', re.I)
INFERENCE = re.compile(r'^(?:are you sure|does|do|would|can|is it true)\b[^.!?\n]{0,120}'
                       r'\b(?:means?|proves?|imply|implies|guarantees?|establish(?:es)?)\b', re.I)
OPERATION = re.compile(r'(?:^|\b(?:and|then|also)\s+)(?:please\s+)?'
                       r'(?:run|execute|install|restart|deploy|delete|save|commit|merge|publish)\b', re.I)
CURRENT_RESEARCH = re.compile(r'\b(?:latest|current|up[- ]to[- ]date|today|browse|search the web|'
                             r'cite (?:official )?sources|source links)\b', re.I)
LIVE_REQUEST = re.compile(r'\b(?:check|show) (?:me )?(?:our|the|current|live)\b|'
                         r'\b(?:are|is|what are) (?:our|my|the current|the live)\b|'
                         r'\b(?:our|my|live|current) (?:workers?|jobs?|tasks?|status)\b', re.I)
PRECISION = re.compile(r'\b(?:explain|compare|comparison|analy[sz]e|calculate|evaluate|research|review|why|how|which|whether|'
                       r'prove|proof|quota|percent(?:age)?|arithmetic)\b|'
                       r'\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)[ -]'
                       r'(?:[a-z]+[ -]){0,2}'
                       r'(?:sentences?|lines?|words?|titles?|options?|items?|examples?)\b', re.I)


def instructions(text):
    """Quoted examples cannot add tool requirements to an answer request."""
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`', '', text)
    return re.sub(r'(?m)^\s*>.*$', '', text)


def requires_execution(text):
    request = instructions(text)
    if re.match(r'^(?:write|draft|compose|explain)\b.{0,50}\b(?:instructions|directions|tutorial|how to)\b', request, re.I):
        return bool(re.search(r'\b(?:then|and)\s+(?:actually|also)\s+(?:run|execute|install)\b', request, re.I))
    return bool(OPERATION.search(request))


def requires_research(text):
    request = instructions(text)
    if (re.search(r'\b(?:supplied|provided) (?:facts|evidence|notes?|data|code)\b', request, re.I)
            and not re.search(r'\b(?:browse|search the web|look up|latest|verify .{0,30}online)\b', request, re.I)):
        return False
    return bool(re.match(r'^(?:research|review|compare)\b', request, re.I)
                and CURRENT_RESEARCH.search(request))


def wants_answer(text):
    """An in-chat deliverable, after explicit tools/targets were checked."""
    from chat_intent import command
    request = re.sub(r'^help me (?:to )?', '', instructions(command(text)), flags=re.I)
    return bool((ANSWER.match(request) or REVISION.match(request) or TEXT_DELIVERABLE.match(request))
                and not ARTIFACT_OPERATION.search(request) and not RETRIEVAL_TARGET.search(request)
                and not requires_execution(request)
                and not requires_research(request))


def conceptual(text):
    """A request to reason about evidence/terms, not observe the live workers."""
    request = instructions(text)
    return bool((CONCEPT.search(request) or INFERENCE.search(request))
                and not LIVE_REQUEST.search(request) and not requires_execution(request))


def needs_precision(text):
    """Reasoning and explicit output constraints merit the calibrated API route.

    This is a quality preference, never permission or a claim that another
    provider cannot answer. Health and hard admission limits still take priority.
    """
    request = instructions(text)
    return bool(PRECISION.search(request) or conceptual(request)
                or (re.search(r'\d', request) and re.search(r'\b(?:cost|price|budget|plan|proposal)\b', request, re.I)))

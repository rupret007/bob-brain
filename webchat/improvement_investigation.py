"""Bounded, source-backed routing investigation; no models or user code run."""
import ast
import hashlib
import json
from pathlib import Path


SOURCES = ('webchat/task_dispatch.py', 'webchat/reply_authority.py',
           'webchat/answer_intent.py', 'webchat/providers.py', 'state/task_queue.py')


def investigate():
    from task_dispatch import parse_work, task_kind
    from answer_intent import conceptual
    from build_info import BUILD
    from source_identity import fingerprint
    root = Path(__file__).resolve().parents[1]
    sources = []
    for name in SOURCES:
        path = root / name
        if path.is_symlink() or path.stat().st_size > 200000:
            raise ValueError('Investigation source is unavailable or oversized: ' + name)
        raw = path.read_bytes()
        tree = ast.parse(raw, filename=name)
        sources.append(dict(path=name, sha256=hashlib.sha256(raw).hexdigest(),
                            functions={node.name:node.lineno for node in tree.body
                                       if isinstance(node, (ast.FunctionDef, ast.ClassDef))}))
    cases = []
    for prompt, expected in (
            ('Write a short thank-you note.', 'answer'),
            ('Compare supplied facts: A costs 10; B costs 12.', 'answer'),
            ('Review the tests and run them', 'coding'),
            ('Research the latest Gemini pricing and cite sources', 'research')):
        task, worker = parse_work(prompt)
        actual = task_kind(task) if task else 'answer'
        cases.append(dict(prompt=prompt, expected=expected, actual=actual, passed=actual == expected))
    prompt = 'Explain the difference between queued and running status.'
    cases.append(dict(prompt=prompt, expected='conceptual answer',
                      actual='conceptual answer' if conceptual(prompt) else 'operational status',
                      passed=conceptual(prompt)))
    payload = dict(build_sha=BUILD['sha'], sources=sources, cases=cases,
                   code_identity=fingerprint(root, 'webchat/test_answer_intent.py'),
                   failed=sum(not row['passed'] for row in cases),
                   scope='Local routing functions and deployed source; no provider answer or external Grok comparison.')
    payload['sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def render(report):
    failures = [row for row in report['cases'] if not row['passed']]
    result = (str(len(report['cases']) - len(failures)) + '/' + str(len(report['cases'])) +
              ' local routing probes matched the intended behavior.')
    if failures:
        result += '\n' + '\n'.join('• ' + row['prompt'] + ': expected ' + row['expected'] +
                                   ', observed ' + row['actual'] + '.' for row in failures)
    else:
        result += (' Writing and supplied comparisons stay in chat; test execution and current-source research '
                   'select capable workers; explaining a status term remains an answer.')
    result += '\nSource evidence: ' + ', '.join('`' + row['path'] + '`' for row in report['sources']) + '.'
    return result

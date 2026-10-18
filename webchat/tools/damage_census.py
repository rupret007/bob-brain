#!/usr/bin/env python3
"""Offline replay of sample raw answers through the delivery path.

Classifies each removed or altered sentence/list item as a correct safety
removal or a false positive. No network. Run from the webchat package path:

  PYTHONPATH=webchat python3 webchat/tools/damage_census.py
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
for folder in (ROOT, REPO / 'services', REPO / 'state'):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import catchup_contract
import claim_evidence
import conversation_focus
import decision_context
import reply_authority
import reply_contract
import resource_decision
from reported_records import units
from unittest.mock import patch

SAMPLES = [
    'WEBBOB-GOAL-1006c-r1-exposed-sample.json',
    'WEBBOB-GOAL-1006c-r1-holdout-sample.json',
    'WEBBOB-GOAL-1006c-r2-exposed-sample.json',
    'WEBBOB-GOAL-1006c-r2-holdout-sample-recovery-1.json',
    'WEBBOB-GOAL-1006c-r3-exposed-sample.json',
    'WEBBOB-GOAL-1006c-r3-holdout-sample.json',
]
SAMPLE_DIR = Path('/Users/jeffstory/Documents/bob-overnight-inject/conductor/goal-1006')

UNSAFE = re.compile(
    r"\b(?:queued|dispatched|assigned|launched|submitted|started execution|"
    r"execution started|I resumed|granted permission|"
    r"hold (?:is |was |has been |now |already )?(?:lifted|cleared|released|expired)|"
    r"(?:lifted|cleared|released) the hold|"
    r"lifts automatically|no longer applies|"
    r"I (?:sent|delivered|enabled|registered|saved) (?:the |a )?(?:hold|message|text)|"
    r"guarantees? (?:zero|equal|equivalent)|"
    r"without (?:extra |additional |any )?(?:charges?|fees?|costs?)|"
    r"zero (?:charges?|fees?|regressions?))\b",
    re.I)
SAFE_HOLD = re.compile(
    r"\b(?:on hold|do(?:es)? not (?:clear|lift|release|override|bypass)|"
    r"remains? (?:paused|held|on hold)|still applies|hold is in place)\b",
    re.I)
EPISTEMIC = re.compile(
    r"\b(?:unverified|not (?:verified|evaluated|established|guaranteed|checked)|"
    r"cannot guarantee|unknown|inventing metrics|non-executing|"
    r"sensible.{0,20}plan|preparatory actions?|scoring rubric)\b",
    re.I)


def _norm(text):
    return re.sub(r'\s+', ' ', re.sub(r'[*_`]', '', text or '')).strip()


def _parts(text):
    return [p for p in units(text or '') if p.strip()]


def classify_drop(raw_unit, stage, reasons):
    text = _norm(raw_unit)
    if UNSAFE.search(text) and not SAFE_HOLD.search(text):
        return 'a'
    if SAFE_HOLD.search(text) and not reply_authority.unnegated_hold_release(text) and not reply_authority.unnegated_execution_start(text):
        return 'b'
    if EPISTEMIC.search(text) and stage in ('claim_evidence', 'empty_labels', 'resource_select', 'count_leadin', 'catchup', 'decision_context'):
        return 'b'
    if any(r in ('unsupported_effect', 'unsupported_permission_change') for r in reasons):
        return 'a'
    if 'unbound_hold_claim' in reasons and SAFE_HOLD.search(text):
        return 'b'
    if stage in ('empty_labels', 'count_leadin', 'decision_context') or 'dependent_on_rejected' in ' '.join(reasons):
        return 'b'
    if UNSAFE.search(text):
        return 'a'
    return 'b'


def reconstruct(tr):
    payload = tr.get('actual_transport_input') or {}
    messages = list(payload.get('messages') or [])
    conversation = dict(id='census', messages=[], intent_state=dict(holds={}))
    user_text = ''
    for i, item in enumerate(messages):
        role = item.get('role') or 'user'
        content = item.get('content') or ''
        msg = dict(id=f'{role[0]}{i}', request_id=f'r{i}', role=role,
                   content=content, status='done', provider='gemini')
        conversation['messages'].append(msg)
        if role == 'user':
            conversation_focus.update(conversation, msg)
            user_text = content
    return conversation, user_text


def replay(raw, conversation, user_text, root):
    assistant = dict(id='aN', request_id=conversation['messages'][-1]['request_id'],
                     role='assistant', content=raw, provider='gemini', status='running')
    conversation['messages'].append(assistant)
    stages = []
    current = raw
    try:
        assistant['_reply_contract'] = reply_contract.derive(conversation, lambda v: v, root)
    except Exception as exc:
        stages.append(('derive', current, current, [type(exc).__name__]))
        assistant['_reply_contract'] = dict(kind='answer', version=1)
    contract = assistant.get('_reply_contract') or {}
    kind = contract.get('kind')
    prior = '\n\n'.join(m.get('content', '') for m in conversation['messages'][:-1]
                        if m.get('role') == 'assistant' and m.get('content'))

    if kind == 'catchup' and contract.get('catchup_projection'):
        before = current
        try:
            current = catchup_contract.render(raw, contract['catchup_projection'], prior=prior)
        except TypeError:
            current = catchup_contract.render(raw, contract['catchup_projection'])
        except Exception as exc:
            current = f'[catchup-error {type(exc).__name__}]'
        if current != before:
            stages.append(('catchup', before, current, ['catchup_contract.render']))
        return current, stages, kind

    if kind == 'resource_advice' and contract.get('resource_projection'):
        before = current
        try:
            current, decision = resource_decision.render(
                raw, contract['resource_projection'], root=root, prior=prior)
            reasons = []
            for block in decision.get('rejected_blocks') or []:
                reasons.append(block.get('reason') or 'unsupported_assertion')
            if current != before:
                stages.append(('resource_select', before, current, reasons or ['resource_decision.render']))
        except Exception as exc:
            current = before
            stages.append(('resource_select', before, current, [type(exc).__name__]))
        before = current
        guarded = reply_authority.enforce(
            root, user_text, dict(content=current, provider='gemini'), conversation,
            observation={}, redact=lambda v: v)
        if guarded != current:
            review = conversation['messages'][-1].get('authority_review') or {}
            reasons = [u.get('reason') for u in review.get('units', []) if not u.get('accepted')]
            stages.append(('reply_authority', current, guarded, reasons or ['enforce']))
            current = guarded
        finished = claim_evidence.finish_delivery(current, source=user_text)
        if finished != current:
            stages.append(('finish_delivery', current, finished, ['finish_delivery']))
            current = finished
    else:
        before = current
        bounded, findings = claim_evidence.deliver(raw, source=user_text, prior=prior)
        if bounded != current:
            cats = []
            for finding in findings or []:
                cats.extend(finding.get('categories') or [])
            stages.append(('claim_evidence', current, bounded, cats or ['claim_evidence.deliver']))
            current = bounded
        before = current
        guarded = reply_authority.enforce(
            root, user_text, dict(content=current, provider='gemini'), conversation,
            observation={}, redact=lambda v: v)
        if guarded != current:
            review = conversation['messages'][-1].get('authority_review') or {}
            reasons = [u.get('reason') for u in review.get('units', []) if not u.get('accepted')]
            stages.append(('reply_authority', current, guarded, reasons or ['enforce']))
            current = guarded
        finished = claim_evidence.finish_delivery(current, source=user_text)
        if finished != current:
            stages.append(('finish_delivery', current, finished, ['finish_delivery']))
            current = finished

    projection = contract.get('decision_context')
    if projection:
        before = current
        rendered, _ = decision_context.render(current, projection, conversation, lambda v: v)
        if rendered != current:
            stages.append(('decision_context', current, rendered, ['decision_context.render']))
            current = rendered
    return current, stages, kind


def diff_units(raw, delivered):
    raw_parts = _parts(raw)
    del_norm = {_norm(p) for p in _parts(delivered)}
    delivered_all = _norm(delivered)
    dropped = []
    altered = []
    for part in raw_parts:
        needle = _norm(part)
        if not needle or len(needle) < 12:
            continue
        if needle in del_norm or needle in delivered_all:
            continue
        # Partial survival (cut/garbled)
        tokens = [t for t in re.findall(r'[a-z0-9]{4,}', needle.lower())]
        overlap = sum(1 for t in tokens if t in delivered_all.lower()) if tokens else 0
        if tokens and overlap / len(tokens) >= 0.6:
            altered.append(part)
        else:
            dropped.append(part)
    return dropped, altered


def load_turns(path):
    data = json.loads(Path(path).read_text())
    by_key = {(t['chain'], t['turn']): t for t in data.get('transports') or []}
    rows = []
    for chain in data.get('chains') or []:
        for index, turn in enumerate(chain.get('turns') or [], 1):
            tr = by_key.get((chain['id'], index))
            if not tr:
                continue
            answer = turn.get('answer') or {}
            delivered = answer.get('content') if isinstance(answer, dict) else answer
            rows.append(dict(
                sample=Path(path).name, chain=chain['id'], turn=index,
                prompt=turn.get('prompt') or '',
                raw=tr.get('raw_answer') or '',
                captured=delivered or '',
                transport=tr,
            ))
    return rows


def main():
    rows = []
    for name in SAMPLES:
        path = SAMPLE_DIR / name
        if path.exists():
            rows.extend(load_turns(path))
    stats = Counter()
    examples = []
    with tempfile.TemporaryDirectory() as folder, \
            patch('live_status_snapshot._screen_sessions', return_value={}), \
            patch('live_status_snapshot.process_table', return_value={}):
        root = Path(folder)
        (root / 'conductor').mkdir(exist_ok=True)
        for row in rows:
            conversation, user_text = reconstruct(row['transport'])
            replayed, stages, kind = replay(row['raw'], conversation, user_text, root)
            source = row['raw']
            if str(row['raw']).lstrip().startswith('{'):
                source = replayed if stages and stages[0][0] in ('catchup', 'resource_select') else row['raw']
                # Diff composed user-facing text against captured delivery when JSON.
                compare_from = stages[0][1] if stages else row['raw']
                if stages and stages[0][0] in ('catchup', 'resource_select'):
                    compare_from = stages[0][2] if stages[0][0] == 'catchup' else row['captured']
            dropped, altered = diff_units(row['raw'] if not str(row['raw']).lstrip().startswith('{') else replayed, replayed)
            # For JSON packets, compare inner composed reasoning against replayed.
            if str(row['raw']).lstrip().startswith('{'):
                dropped, altered = [], []
                # Use captured vs replayed only to list remaining damage vs original capture;
                # classify using stage diffs against the first composed form.
                composed = None
                for stage, before, after, reasons in stages:
                    if stage in ('resource_select', 'catchup'):
                        composed = after
                        lost, changed = diff_units(before if stage == 'catchup' else _reasoning_from_raw(row['raw']), after)
                        for part in lost + changed:
                            kind_ab = classify_drop(part, stage, reasons)
                            stats[kind_ab] += 1
                            stats['total'] += 1
                            stats['stage:' + stage] += 1
                            examples.append((kind_ab, row, stage, part, reasons))
                        break
                if composed is None:
                    lost, changed = diff_units(row['captured'], replayed)
                else:
                    lost, changed = [], []
                for stage, before, after, reasons in stages:
                    if stage in ('resource_select', 'catchup'):
                        continue
                    lost, changed = diff_units(before, after)
                    for part in lost + changed:
                        kind_ab = classify_drop(part, stage, reasons)
                        stats[kind_ab] += 1
                        stats['total'] += 1
                        stats['stage:' + stage] += 1
                        examples.append((kind_ab, row, stage, part, reasons))
                continue
            for stage, before, after, reasons in stages:
                lost, changed = diff_units(before, after)
                for part in lost + changed:
                    kind_ab = classify_drop(part, stage, reasons)
                    stats[kind_ab] += 1
                    stats['total'] += 1
                    stats['stage:' + stage] += 1
                    examples.append((kind_ab, row, stage, part, reasons))
            if not stages:
                lost, changed = diff_units(row['raw'], replayed)
                for part in lost + changed:
                    stats['b'] += 1
                    stats['total'] += 1
                    examples.append(('b', row, 'unknown', part, []))

    print('CENSUS turns', len(rows), 'unit-changes', stats['total'])
    print('  (a) correctly removed', stats['a'])
    print('  (b) false positives  ', stats['b'])
    print('  by stage:', {k[6:]: n for k, n in stats.items() if k.startswith('stage:')})
    print('\nFalse-positive samples (truncated):')
    shown = 0
    for kind_ab, row, stage, part, reasons in examples:
        if kind_ab != 'b':
            continue
        shown += 1
        if shown > 24:
            print('  ...')
            break
        snippet = _norm(part)[:180]
        print(f"  [{row['sample'].replace('WEBBOB-GOAL-1006c-','')}] {row['chain']} T{row['turn']} @{stage} {reasons}: {snippet}")
    return 0


def _reasoning_from_raw(raw):
    try:
        value = json.loads(raw)
    except Exception:
        return raw
    answer = value.get('answer') if isinstance(value, dict) else None
    if isinstance(answer, list):
        bits = []
        for block in answer:
            if isinstance(block, dict) and 'reasoning' in block:
                bits.append(block['reasoning'])
        return '\n\n'.join(bits) or raw
    if isinstance(answer, str):
        return re.sub(r'\[fact:[^\]]+\]', '', answer)
    return raw


if __name__ == '__main__':
    raise SystemExit(main())

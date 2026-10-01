"""Observe explicitly bound historical receiver evidence without consuming work.

The private server configuration attests owner-reported provenance. Checkpoint
and journal checks establish correspondence, not native reasoning or availability.
Neither a cursor nor a file naming itself Grok establishes that provenance.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat


CONFIG = Path('conductor/webchat/receiver-evidence.json')
PROVENANCE = 'owner_supplied_native_registered_computer_response'


def _read(root, relative, limit):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Uncontained evidence')
    target = root / path
    if any((root / parent).is_symlink() for parent in (path, *path.parents)):
        raise ValueError('Symlink evidence')
    descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size > limit):
            raise ValueError('Unsafe evidence file')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Oversized evidence')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Invalid evidence object')
    return value, raw


def observe(root):
    """Return bounded metadata only; no raw events, writes, ACKs or dispatch."""
    root = Path(root)
    result = dict(historical_checkpoint_ack_verified=False,
                  current_availability='unknown', automatic_delivery_verified=False)
    if not (root / CONFIG).exists():
        return dict(result, evidence_status='not_configured')
    try:
        binding, _ = _read(root, CONFIG, 4096)
        if binding.get('schema_version') != 1 or binding.get('provenance') != PROVENANCE:
            raise ValueError('Unattested provenance')
        proof_path = Path(binding['proof_path'])
        if proof_path.parent != Path('conductor/reviews'):
            raise ValueError('Uncontained proof')
        proof, raw = _read(root, proof_path, 16384)
        if hashlib.sha256(raw).hexdigest() != binding['proof_sha256']:
            raise ValueError('Proof changed')
        if proof.get('passed') is not True or proof.get('native_checkpoint_ack_verified') is not True:
            raise ValueError('Unverified proof')
        checkpoint_path = Path(proof['checkpoint']).relative_to(root)
        if checkpoint_path.parent != Path('conductor/state/grok-receiver'):
            raise ValueError('Uncontained checkpoint')
        page, raw = _read(root, checkpoint_path, 256 * 1024)
        if len(raw) != proof['checkpoint_bytes'] or hashlib.sha256(raw).hexdigest() != proof['checkpoint_sha256']:
            raise ValueError('Checkpoint changed')
        start, end, events = page['since_seq'], page['through_seq'], page['events']
        if (type(start) is not int or type(end) is not int or not 0 <= start < end or
                not isinstance(events, list) or not 1 <= len(events) <= 80 or
                len(events) != proof['event_count']):
            raise ValueError('Invalid checkpoint range')
        payload = {key: page[key] for key in ('journal_id', 'since_seq', 'through_seq', 'events')}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        receipt = proof['receipt']
        if (digest != page['receipt_sha256'] or any(receipt[key] != page[key] for key in
                ('since_seq', 'through_seq', 'receipt_sha256')) or
                not isinstance(receipt.get('acknowledged_at'), str) or not receipt['acknowledged_at']):
            raise ValueError('Unbound acknowledgment')
        import alignment_events
        retained = alignment_events.catchup_page(root, since_seq=start, limit=len(events))
        if any(retained[key] != page[key] for key in payload) or retained['receipt_sha256'] != digest:
            raise ValueError('Checkpoint differs from retained journal')
        state, _ = _read(root, Path('conductor/state/STATE.json'), 2 * 1024 * 1024)
        cursor = state.get('bob_coordination_ack_seq')
        if type(cursor) is not int or cursor < end:
            raise ValueError('Acknowledgment is no longer present')
        # A duplicate or empty-page ACK legitimately replaces the last receipt.
        # Corroborate that current receipt without rewriting historical evidence.
        latest = state.get('bob_coordination_last_receipt') or {}
        latest_start = latest.get('since_seq')
        if type(latest_start) is not int or not 0 <= latest_start <= cursor or latest.get('through_seq') != cursor:
            raise ValueError('Invalid current acknowledgment')
        current_page = alignment_events.catchup_page(root, since_seq=latest_start, limit=80)
        current_events = [event for event in current_page['events'] if event['seq'] <= cursor]
        if latest_start < cursor and (not current_events or current_events[-1]['seq'] != cursor):
            raise ValueError('Current acknowledgment exceeds its retained batch')
        current_payload = dict(journal_id=current_page['journal_id'], since_seq=latest_start,
                               through_seq=cursor, events=current_events)
        current_digest = hashlib.sha256(json.dumps(current_payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if current_digest != latest.get('receipt_sha256'):
            raise ValueError('Current acknowledgment differs from retained records')
        at = proof['at']
        if type(at) not in (int, float) or not math.isfinite(at) or at <= 0:
            raise ValueError('Invalid observation time')
        if any(type(page[key]) is not bool or proof[key] != page[key] for key in ('history_gap', 'has_more')):
            raise ValueError('Invalid coverage evidence')
        return dict(result, historical_checkpoint_ack_verified=True, evidence_status='verified',
                    provenance=PROVENANCE, observed_at=at, since_seq=start, through_seq=end,
                    receipt_sha256=digest, event_count=len(events), history_gap=page['history_gap'],
                    has_more_at_checkpoint=page['has_more'])
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return dict(result, evidence_status='unavailable_or_invalid')


def describe(observation):
    if observation['historical_checkpoint_ack_verified']:
        return (f"The owner-reported Grok checkpoint and acknowledgment through record {observation['through_seq']} "
                'match the retained work record. Newer batches still need their own receiver checkpoint and acknowledgment. '
                'That earlier check does not establish full catch-up, current availability, automatic wake-up or execution.')
    return ('A native Grok checkpoint and acknowledgment are not verified by the currently available evidence. '
            'The receiver still needs to read a batch, save its own checkpoint, and acknowledge that exact batch. '
            'Current availability and automatic wake-up remain unknown.')

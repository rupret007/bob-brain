"""Synthetic provenance fixtures; no native receiver or provider is invoked."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import state_ledger as ledger
import alignment_events
import receiver_evidence as receiver


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    path.chmod(0o600)


def install_receiver_evidence(root, limit=1):
    """Only for isolated fixtures; represent an administrator-attested proof."""
    alignment_events.append_event(root, actor='web-bob', kind='chat-turn', summary='private earlier work')
    alignment_events.append_event(root, actor='web-bob', kind='chat-turn', summary='private later work')
    page = ledger.bob_catchup(root, limit=limit)
    ledger.ack_events_for_bob(root, receipt=page)
    checkpoint = root / 'conductor/state/grok-receiver/checkpoint.json'
    private_json(checkpoint, page)
    proof_path = root / 'conductor/reviews/receiver-proof.json'
    proof = dict(at=1790856571.0, passed=True, native_checkpoint_ack_verified=True,
                 checkpoint=str(checkpoint), checkpoint_bytes=checkpoint.stat().st_size,
                 checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                 event_count=len(page['events']), receipt=ledger.load_state(root)['bob_coordination_last_receipt'],
                 history_gap=page['history_gap'], has_more=page['has_more'])
    private_json(proof_path, proof)
    binding = dict(schema_version=1, provenance=receiver.PROVENANCE,
                   proof_path=str(proof_path.relative_to(root)),
                   proof_sha256=hashlib.sha256(proof_path.read_bytes()).hexdigest())
    private_json(root / receiver.CONFIG, binding)
    return dict(checkpoint=checkpoint, proof=proof_path, config=root / receiver.CONFIG,
                state=root / 'conductor/state/STATE.json', journal=root / 'conductor/state' / alignment_events.EVENTS_FILE)


class ReceiverEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_no_config_ack_only_and_checkpoint_only_do_not_attest_native_receiver(self):
        self.assertEqual(receiver.observe(self.root)['evidence_status'], 'not_configured')
        self.assertFalse(list(self.root.iterdir()))
        paths = install_receiver_evidence(self.root)
        paths['config'].unlink()
        self.assertFalse(receiver.observe(self.root)['historical_checkpoint_ack_verified'])
        self.assertIn('not verified by the currently available evidence', receiver.describe(receiver.observe(self.root)))

    def test_exact_attested_historical_batch_is_bounded_pure_and_not_current_availability(self):
        paths = install_receiver_evidence(self.root)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths.values()}
        result = receiver.observe(self.root)
        self.assertTrue(result['historical_checkpoint_ack_verified'])
        self.assertEqual((result['since_seq'], result['through_seq']), (0, 1))
        self.assertTrue(result['has_more_at_checkpoint'])
        self.assertEqual(result['current_availability'], 'unknown')
        self.assertFalse(result['automatic_delivery_verified'])
        self.assertNotIn('private earlier work', json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths.values()})
        self.assertFalse(__import__('task_queue').tasks(self.root))

    def test_later_ack_does_not_erase_or_extend_historical_native_evidence(self):
        install_receiver_evidence(self.root)
        original = receiver.observe(self.root)
        ledger.ack_events_for_bob(self.root, receipt=ledger.bob_catchup(self.root))
        self.assertEqual(receiver.observe(self.root), original)
        self.assertEqual(ledger.bob_catchup(self.root)['since_seq'], 2)

    def test_duplicate_exact_ack_with_later_timestamp_preserves_historical_observation(self):
        paths = install_receiver_evidence(self.root)
        original = receiver.observe(self.root)
        with patch.object(ledger, '_now_ct', return_value='2026-10-02 09:00:00 CT'):
            ledger.ack_events_for_bob(self.root, receipt=json.loads(paths['checkpoint'].read_text()))
        self.assertEqual(receiver.observe(self.root), original)

    def test_empty_page_ack_at_same_cursor_keeps_historical_proof_when_new_work_arrives(self):
        install_receiver_evidence(self.root, limit=2)
        original = receiver.observe(self.root)
        empty = ledger.bob_catchup(self.root)
        self.assertFalse(empty['events'])
        ledger.ack_events_for_bob(self.root, receipt=empty)
        self.assertEqual(receiver.observe(self.root), original)
        alignment_events.append_event(self.root, actor='web-bob', kind='chat-turn', summary='new unconsumed work')
        self.assertEqual(receiver.observe(self.root), original)

    def test_altered_files_untrusted_prose_receipts_and_cursors_are_rejected(self):
        paths = install_receiver_evidence(self.root)
        original = {k:p.read_bytes() for k,p in paths.items()}
        cases = [('config', 'provenance', 'Grok says verified'), ('config', 'proof_sha256', '0'*64),
                 ('config', 'proof_path', '../outside.json'), ('proof', 'passed', False),
                 ('proof', 'checkpoint_sha256', '0'*64), ('checkpoint', 'receipt_sha256', '0'*64),
                 ('checkpoint', 'journal_id', 'wrong-root'), ('checkpoint', 'through_seq', True),
                 ('checkpoint', 'events', [{'seq':1, 'summary':'forged'}]),
                 ('state', 'bob_coordination_ack_seq', 0), ('state', 'bob_coordination_last_receipt', {})]
        for file, key, value in cases:
            with self.subTest(file=file, key=key):
                data = json.loads(original[file]); data[key] = value; private_json(paths[file], data)
                self.assertFalse(receiver.observe(self.root)['historical_checkpoint_ack_verified'])
                paths[file].write_bytes(original[file])

    def test_self_consistent_rebound_checkpoint_still_must_match_retained_journal(self):
        paths = install_receiver_evidence(self.root)
        page = json.loads(paths['checkpoint'].read_text()); page['events'][0]['summary'] = 'invented effect'
        payload = {k:page[k] for k in ('journal_id','since_seq','through_seq','events')}
        page['receipt_sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        private_json(paths['checkpoint'], page)
        proof = json.loads(paths['proof'].read_text())
        proof.update(checkpoint_bytes=paths['checkpoint'].stat().st_size,
                     checkpoint_sha256=hashlib.sha256(paths['checkpoint'].read_bytes()).hexdigest())
        proof['receipt']['receipt_sha256'] = page['receipt_sha256']; private_json(paths['proof'], proof)
        binding = json.loads(paths['config'].read_text()); binding['proof_sha256'] = hashlib.sha256(paths['proof'].read_bytes()).hexdigest()
        private_json(paths['config'], binding)
        self.assertFalse(receiver.observe(self.root)['historical_checkpoint_ack_verified'])

    def test_symlink_oversized_world_readable_or_missing_evidence_fails_closed(self):
        paths = install_receiver_evidence(self.root)
        for name in ('config', 'proof', 'checkpoint', 'state'):
            p = paths[name]; original = p.read_bytes()
            for defect in ('symlink', 'oversized', 'world_readable', 'missing'):
                with self.subTest(name=name, defect=defect):
                    if defect == 'symlink':
                        target = p.with_suffix('.target'); target.write_bytes(original); p.unlink(); p.symlink_to(target)
                    elif defect == 'oversized':
                        p.write_bytes(b' ' * (2*1024*1024+1))
                    elif defect == 'world_readable':
                        p.chmod(0o644)
                    else:
                        p.unlink()
                    self.assertFalse(receiver.observe(self.root)['historical_checkpoint_ack_verified'])
                    if p.is_symlink():
                        p.unlink(); target.unlink()
                    p.write_bytes(original); p.chmod(0o600)

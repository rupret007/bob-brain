"""Offline outage/reconnect evidence, exact batch ACKs and legacy identities."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

from app import state_ledger as ledger
import alignment_events as events
from test_webbob_replyq_1856 import SessionFixture
from providers import Providers


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'conductor/state' / events.EVENTS_FILE

    def add(self, summary, kind='chat-turn'):
        return events.append_event(self.root, actor='web-bob', kind=kind, summary=summary)

    def test_long_outage_retains_more_than_old_rotation_boundary(self):
        self.path.parent.mkdir(parents=True)
        original = ''.join(json.dumps(dict(seq=i, summary=f'work {i}')) + '\n' for i in range(1, 2002))
        self.path.write_text(original)
        self.assertEqual(self.add('new work'), 2002)
        self.assertTrue(self.path.read_text().startswith(original))
        self.assertEqual(events.read_events_page(self.root, page_size=3)['high_seq'], 3)
        self.assertEqual(events.catchup_page(self.root, since_seq=2001)['events'][0]['summary'], 'new work')

    def test_retained_legacy_duplicates_and_missing_identity_are_not_dropped(self):
        self.path.parent.mkdir(parents=True)
        rows = [dict(seq=1999, summary='a'), dict(seq=2001, summary='b'),
                dict(seq=2001, summary='c'), dict(summary='manual record'), dict(seq=2001, summary='d')]
        original = ''.join(json.dumps(row) + '\n' for row in rows)
        self.path.write_text(original)
        page = events.catchup_page(self.root, since_seq=2001)
        self.assertEqual([row['summary'] for row in page['events']], ['c', 'manual record', 'd'])
        self.assertEqual([row['seq'] for row in page['events']], [2002, 2003, 2004])
        self.assertEqual(page['events'][0]['legacy_seq'], 2001)
        self.assertEqual(self.add('e'), 2005)
        self.assertTrue(self.path.read_text().startswith(original))
        self.assertTrue(events.catchup_page(self.root, since_seq=0)['history_gap'])

    def test_read_is_pure_and_never_implies_availability_or_consumption(self):
        self.assertEqual(ledger.bob_catchup(self.root)['events'], [])
        self.assertFalse(list(self.root.rglob('*')))
        self.add('recorded while Grok unavailable')
        before = self.path.read_bytes()
        first = ledger.bob_catchup(self.root)
        self.assertEqual(first, ledger.bob_catchup(self.root))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse((self.root / ledger.LAST_SEEN).exists())

    def test_local_receiver_cli_consumes_only_exact_checkpointed_page(self):
        self.add('first work record')
        command = [sys.executable, str(Path(events.__file__).with_name('bob_sync.py')),
                   '--root', str(self.root)]
        read = subprocess.run(command + ['read'], capture_output=True, text=True, check=True)
        receipt = json.loads(read.stdout)
        self.assertEqual(receipt['through_seq'], 1)
        self.assertFalse((self.path.parent / ledger.STATE_FILE).exists())
        self.add('arrived while receiver persisted its checkpoint')
        result = subprocess.run(command + ['ack'], input=read.stdout, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), dict(acknowledged_through=1, execution_started=False))
        remaining = ledger.bob_catchup(self.root)
        self.assertEqual([event['seq'] for event in remaining['events']], [2])
        bad = subprocess.run(command + ['ack'], input='{}', capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(ledger.bob_catchup(self.root), remaining)
        self.assertFalse(__import__('task_queue').tasks(self.root))

    def test_acknowledgment_is_bound_to_the_batch_read_before_new_arrivals(self):
        self.add('completed artifact A')
        receipt = ledger.bob_catchup(self.root)
        self.add('completed artifact B')
        ledger.write_catchup(self.root)
        self.assertEqual(ledger.ack_events_for_bob(self.root, receipt=receipt), 1)
        self.assertEqual([e['summary'] for e in ledger.bob_catchup(self.root)['events']], ['completed artifact B'])
        self.assertEqual(ledger.ack_events_for_bob(self.root, receipt=receipt), 1)
        self.assertEqual(ledger.load_state(self.root)['bob_coordination_ack_seq'], 1)

    def test_unbound_future_skipped_and_modified_receipts_are_refused(self):
        for i in range(4):
            self.add(str(i))
        with self.assertRaises(ValueError):
            ledger.ack_events_for_bob(self.root)
        with self.assertRaises(ValueError):
            ledger.ack_events_for_bob(self.root, seq=10000)
        page = events.catchup_page(self.root, since_seq=2)
        with self.assertRaises(ValueError):
            ledger.ack_events_for_bob(self.root, receipt=page)
        page = ledger.bob_catchup(self.root)
        tampered = copy.deepcopy(page)
        tampered['events'][0]['summary'] = 'invented completion'
        with self.assertRaises(ValueError):
            ledger.ack_events_for_bob(self.root, receipt=tampered)
        self.assertFalse(ledger.load_state(self.root).get('bob_coordination_ack_seq'))

    def test_old_ack_retry_preserves_latest_receipt_and_legacy_watermark(self):
        marker = self.root / ledger.LAST_SEEN
        marker.parent.mkdir(parents=True)
        marker.write_text('legacy receiver checkpoint')
        before = marker.stat().st_mtime_ns
        self.add('one')
        first = ledger.bob_catchup(self.root)
        ledger.ack_events_for_bob(self.root, receipt=first)
        self.add('two')
        second = ledger.bob_catchup(self.root)
        ledger.ack_events_for_bob(self.root, receipt=second)
        latest = ledger.load_state(self.root)['bob_coordination_last_receipt']
        self.assertEqual(ledger.ack_events_for_bob(self.root, receipt=first), 2)
        self.assertEqual(ledger.load_state(self.root)['bob_coordination_last_receipt'], latest)
        self.assertEqual(marker.read_text(), 'legacy receiver checkpoint')
        self.assertEqual(marker.stat().st_mtime_ns, before)

    def test_interrupted_utf8_append_is_unavailable_without_changing_history(self):
        self.add('retained work')
        with self.path.open('ab') as out:
            out.write(b'{"summary":"interrupted \xe2')
        original = self.path.read_bytes()
        with self.assertRaises(OSError):
            ledger.bob_catchup(self.root)
        with self.assertRaises(OSError):
            self.add('later work')
        self.assertEqual(self.path.read_bytes(), original)

    def test_summary_never_acknowledges_events_hidden_by_many_blockers(self):
        for i in range(18):
            self.add(f'work {i}', kind='custom-kind')
        state = ledger.default_state()
        state['open_asks'] = [dict(id=str(i), body=f'blocker {i}', status='new') for i in range(35)]
        ledger.save_state(self.root, state)
        with patch.object(ledger, '_commits_since', return_value=[]):
            ledger.write_catchup(self.root)
        summary = (self.path.parent / 'BOB-CATCHUP.md').read_text()
        for i in range(1, 13):
            self.assertIn(f'Event {i}: custom-kind', summary)
        self.assertNotIn('Event 13:', summary)
        self.assertEqual(ledger.load_state(self.root)['last_coordination_event_seq'], 12)
        self.assertEqual(len([line for line in summary.splitlines() if line.startswith('- ')]), 25)

    def test_truncated_history_cannot_validate_an_old_receipt(self):
        self.add('first')
        self.add('second')
        receipt = ledger.bob_catchup(self.root)
        # Simulate an unsupported legacy publisher trimming history after read.
        self.path.write_text(self.path.read_text().splitlines(keepends=True)[-1])
        with self.assertRaises(ValueError):
            ledger.ack_events_for_bob(self.root, receipt=receipt)
        self.assertFalse(ledger.load_state(self.root).get('bob_coordination_ack_seq'))

    def test_cutover_preserves_legacy_bytes_and_new_history_survives_old_writer(self):
        self.path.parent.mkdir(parents=True)
        legacy = self.path.parent / events.LEGACY_EVENTS_FILE
        raw = json.dumps(dict(seq=2001, summary='last retained v1 work')).encode()
        legacy.write_bytes(raw)  # Old manual writer omitted the trailing newline.
        before = ledger.bob_catchup(self.root)
        self.assertEqual(self.add('new durable work'), 2002)
        self.assertEqual(legacy.read_bytes(), raw)
        self.assertTrue(self.path.read_bytes().startswith(raw + b'\n'))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        legacy.write_text(json.dumps(dict(seq=2001, summary='old writer replaced v1')) + '\n')
        self.assertEqual(ledger.ack_events_for_bob(self.root, receipt=before), 2001)
        self.assertEqual(ledger.bob_catchup(self.root)['events'][0]['summary'], 'new durable work')

    def test_fresh_journal_is_private_and_corrupt_shared_state_cannot_be_reset_by_ack(self):
        self.add('result')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        receipt = ledger.bob_catchup(self.root)
        state_path = self.path.parent / ledger.STATE_FILE
        state_path.write_bytes(b'{corrupted original state')
        original = state_path.read_bytes()
        with self.assertRaises(ValueError):
            ledger.ack_events_for_bob(self.root, receipt=receipt)
        self.assertEqual(state_path.read_bytes(), original)
        self.assertFalse((self.root / ledger.LAST_SEEN).exists())

    def test_result_record_preserves_verification_limits_and_does_not_copy_claim_tokens(self):
        result = 'A useful completed report'
        digest = hashlib.sha256(result.encode()).hexdigest()
        row = dict(id='job-1', status='succeeded', result=result, result_sha256=digest,
                   acceptance=dict(accepted=True, method='verified-execution', result_sha256=digest),
                   claim_token='never-copy-this-claim')
        first = events.record_task_result(self.root, row)
        self.assertEqual(events.record_task_result(self.root, row), first)
        saved = events.read_events(self.root)[0]
        self.assertTrue(saved['outcome']['accepted_result'])
        self.assertNotIn('never-copy-this-claim', self.path.read_text())
        row.update(id='job-2', acceptance=dict(accepted=True, result_sha256='wrong'))
        events.record_task_result(self.root, row)
        self.assertFalse(events.read_events(self.root)[-1]['outcome']['accepted_result'])


class ProductCoordinationTests(SessionFixture):
    REQUEST = 'I want it to be able to coordinate with Grok when Grok Bot is available and when it’s not have a record of what was done so when it comes back up it can catch up.'

    def test_owner_need_prepares_exact_batch_without_receiver_effect_and_survives_retry(self):
        import uuid
        from app import Chat
        for i in range(14):
            events.append_event(self.root, actor='web-bob', kind='answer-delivered',
                                summary=f'Other conversation private source {i}')
        before = ledger.bob_catchup(self.root)
        request = str(uuid.uuid4())
        public = self.chat.submit(self.identifier, self.REQUEST, request)
        answer = public['messages'][-1]
        self.assertEqual(answer['provider'], 'coordination')
        self.assertEqual(answer['coordination_receipt']['record_count'], 12)
        self.assertTrue(answer['coordination_receipt']['has_more'])
        self.assertFalse(answer['coordination_receipt']['acknowledged'])
        self.assertIn('earlier recorded updates', answer['content'])
        self.assertIn('receiver is still unverified', answer['content'])
        self.assertEqual(self.chat.get(self.identifier)['_coordination_prepared_batches'][request], before)
        self.assertNotIn('_coordination_prepared_batches', public)
        self.assertNotIn('Other conversation private source', json.dumps(public))
        provider = Providers(self.root, self.chat.redact)
        self.assertNotIn('Other conversation private source', provider.prompt(self.chat.get(self.identifier), fast=True))
        self.assertEqual(ledger.bob_catchup(self.root)['since_seq'], 0)
        self.assertFalse(self.fake.calls)
        self.assertFalse(__import__('task_queue').tasks(self.root))
        ledger.ack_events_for_bob(self.root, receipt=before)
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        retried = self.chat.submit(self.identifier, self.REQUEST, request)
        self.assertEqual(retried['messages'], public['messages'])
        self.assertEqual(self.chat.get(self.identifier)['_coordination_prepared_batches'][request], before)

    def test_preparation_handles_empty_and_corrupt_records_without_claiming_ack(self):
        answer = self.send(self.REQUEST)
        self.assertEqual(answer['coordination_receipt']['record_count'], 0)
        self.assertIn('empty catch-up batch', answer['content'])
        path = self.root / 'conductor/state' / events.EVENTS_FILE
        path.write_bytes(b'broken journal\n')
        answer = self.send(self.REQUEST)
        self.assertNotIn('coordination_receipt', answer)
        self.assertIn('could not prepare', answer['content'])
        self.assertEqual(path.read_bytes(), b'broken journal\n')

    def test_failed_preparation_save_does_not_publish_success_or_consume_retry(self):
        import uuid
        request = str(uuid.uuid4())
        with patch('app.private_write', side_effect=OSError('storage unavailable')):
            with self.assertRaises(OSError):
                self.chat.submit(self.identifier, self.REQUEST, request)
        self.assertFalse(any(m.get('request_id') == request for m in self.chat.get(self.identifier)['messages']))
        result = self.chat.submit(self.identifier, self.REQUEST, request)
        self.assertEqual(result['messages'][-1]['coordination_receipt']['completed_step'], 'prepared_local_catchup_batch')
        self.assertFalse((self.root / ledger.LAST_SEEN).exists())

    def test_preparation_does_not_intercept_negative_quoted_or_mixed_execution(self):
        from capabilities import prepare_coordination
        value = self.chat.get(self.identifier)
        for text in ('Can you interface with Grok Bot?',
                     'I want no Grok integration; write a poem.',
                     'Explain this quote: "I want Web Bob to coordinate with Grok."',
                     'I want it to coordinate with Grok, but do not start anything; just explain.',
                     'I want Web Bob to coordinate with Grok eventually; for now, just describe how it would work.',
                     'I want Web Bob to coordinate with Grok only after I approve it.',
                     'I want Web Bob to coordinate with Grok and write a poem.',
                     'I want Web Bob to coordinate with Grok and delete old files.'):
            with self.subTest(text=text):
                self.assertIsNone(prepare_coordination(self.chat, value, text, 'unused'))
        value['_coordination_excluded'] = True
        self.assertIsNone(prepare_coordination(self.chat, value, self.REQUEST, 'unused'))
        self.assertFalse(events.read_events(self.root))

    def test_legacy_or_unbound_voice_entries_do_not_create_scope_or_answer_receipts(self):
        value = self.chat.get(self.identifier)
        value.pop('intent_state')
        value['messages'] = [dict(role='user', content='old unbound request', id='u', status='done'),
                             dict(role='assistant', content='old answer', id='a', status='done')]
        self.chat.save(value)
        self.assertFalse(events.read_events(self.root))
        self.assertEqual(self.chat.get(self.identifier)['messages'], value['messages'])

    def test_unreadable_projection_keeps_authoritative_reply_and_pending_outbox(self):
        self.fake.reply_text = 'Useful answer kept despite a broken shared journal'
        path = self.root / 'conductor/state' / events.EVENTS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'{"summary":"interrupted \xe2')
        original = path.read_bytes()
        self.send('Write a note for the meeting.')
        value = self.chat.get(self.identifier)
        self.assertEqual(value['messages'][-1]['status'], 'done')
        self.assertEqual(value['messages'][-1]['content'], self.fake.reply_text)
        self.assertTrue(value['_coordination_outbox'])
        self.assertEqual(path.read_bytes(), original)

    def test_drill_context_stays_excluded_after_clear_and_restart(self):
        from app import Chat
        overlay = self.root / 'isolated-drill'
        self.chat.overlay_roots[self.identifier] = overlay
        value = self.chat.get(self.identifier)
        value['messages'] = [dict(role='user', content='private fixture', id='u', request_id='r', status='done'),
                             dict(role='assistant', content='fixture answer', id='a', request_id='r', status='done')]
        with patch.object(events, 'append_event', side_effect=OSError('unavailable')):
            self.chat.save(value)
        self.chat.clear_drill_overlay(self.identifier)
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        recovered = self.chat.get(self.identifier)
        self.chat.save(recovered)
        self.assertTrue(recovered['_coordination_excluded'])
        self.assertNotIn('_coordination_excluded', self.chat.public(recovered))
        self.assertFalse(events.read_events(self.root))
        self.assertFalse(events.read_events(overlay))

    def test_failed_answer_publication_survives_next_turn_and_restart(self):
        from app import Chat
        self.fake.reply_text = 'First useful draft'
        with patch.object(events, 'append_event', side_effect=OSError('storage unavailable')):
            self.send('Write a note for the meeting.')
            self.send('Hold WebJam.')
        value = self.chat.get(self.identifier)
        self.assertTrue(value['_coordination_outbox'])
        self.assertNotIn('_coordination_outbox', self.chat.public(value))
        self.chat.close()
        self.chat = Chat(self.folder, self.root, self.fake)
        rows = events.read_events(self.root, limit=80)
        self.assertTrue(any(r.get('answer_excerpt') == 'First useful draft' for r in rows))
        self.assertTrue(any(r['kind'] == 'scope-change' and 'WebJam' in r['saved_scope']['holds'] for r in rows))
        self.assertFalse(self.chat.get(self.identifier)['_coordination_outbox'])
        self.assertFalse(__import__('task_queue').tasks(self.root))

    def test_private_texting_content_never_enters_shared_projection(self):
        value = self.chat.get(self.identifier)
        value['messages'] = [dict(role='user', content='private message', id='u', request_id='r',
                                  status='done', texting=True),
                             dict(role='assistant', content='private reply', id='a', request_id='r',
                                  status='done', texting=True)]
        self.chat.save(value)
        self.assertFalse(events.read_events(self.root))

    def test_owner_interface_question_gets_implemented_metadata_without_unrelated_history(self):
        self.send('Can you interface with grok bot?  The point of this is to be able to use this rather than grok.')
        provider = Providers(self.root, self.chat.redact)
        with patch.object(provider, 'snapshot', side_effect=AssertionError('irrelevant operational snapshots')):
            prompt = provider.prompt(self.chat.get(self.identifier), fast=True)
        self.assertIn('implemented Web Bob capability metadata', prompt)
        self.assertIn('exact-batch acknowledgment', prompt)
        self.assertIn('automatic wake-up', prompt)
        self.assertIn('unverified', prompt)
        self.send('I want it to be able to coordinate with Grok when Grok Bot is available and when it’s not have a record of what was done so when it comes back up it can catch up.')
        prompt = provider.prompt(self.chat.get(self.identifier), fast=True)
        self.assertIn('durable_shared_records_implemented', prompt)
        self.assertIn('saved_conversation_receipts', prompt)
        self.assertIn('answer-delivered', prompt)
        self.assertIn('Reuse the', prompt)
        self.send('Write a poem about the lake.')
        prompt = provider.prompt(self.chat.get(self.identifier), fast=True)
        self.assertNotIn('implemented Web Bob capability metadata', prompt)
        self.assertFalse(__import__('task_queue').tasks(self.root))

    def test_mentioned_integrations_do_not_displace_unrelated_writing_or_quotes(self):
        provider = Providers(self.root, self.chat.redact)
        for text in ('I want no Grok integration; write a two-line poem about rain.',
                     'I want a fictional story about Grok connecting two islands.',
                     'Explain this quote: "I want Web Bob to coordinate with Grok."'):
            with self.subTest(text=text):
                self.send(text)
                prompt = provider.prompt(self.chat.get(self.identifier), fast=True)
                self.assertNotIn('implemented Web Bob capability metadata', prompt)
        self.assertFalse(__import__('task_queue').tasks(self.root))

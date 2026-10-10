"""Calendar and PR2 routing tests: every external side effect is injected."""
import copy
import concurrent.futures
from datetime import datetime
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
import uuid

from app import Chat
from calendar_actions import (CalendarActions, CalendarError, CalendarHTTPError, GoogleCalendar,
                              NEEDS_AUTH, UNCERTAIN, CANCEL_UNCERTAIN, event_spec, request_json)
from reminders import ZONE
from task_dispatch import task_queue
from texting import BlueBubbles, Texting, TextingError
from texting_fixture import OfflineProviders


class FakeCalendar:
    def __init__(self):
        self.creates = []
        self.reads = []
        self.response = {'items': []}
        self.error = None
        self.event = dict(id='event123', etag='"v7"', status='confirmed', summary='Dentist',
                          visibility='private', organizer={'self': True},
                          start={'dateTime': '2026-10-11T14:00:00-05:00'},
                          end={'dateTime': '2026-10-11T14:30:00-05:00'})
        self.get = Mock(side_effect=lambda _event_id: copy.deepcopy(self.event))
        self.delete = Mock(return_value={'http_status': 204})

    def configured(self):
        if self.error:
            raise CalendarError(self.error)

    def create(self, event):
        self.creates.append(copy.deepcopy(event))
        return dict(event, status='confirmed')

    def listing(self, start, end):
        self.reads.append((start, end))
        return self.response


class CalendarFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 10, 10, 1, 47, tzinfo=ZONE).timestamp()
        self.client = FakeCalendar()
        self.actions = CalendarActions(self.root, self.client, lambda: self.now)
        self.state = {'holds': {}, 'last_permission': None}
        # Fail loudly on any accidental live transport, including localhost.
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.notify = patch('reminders.notify_macos', side_effect=AssertionError('Notification forbidden'))
        self.notify.start()
        self.addCleanup(self.notify.stop)

    def say(self, text, cid='chat', request_id=None):
        return self.actions.handle(text, cid, request_id or str(uuid.uuid4()), self.state)

    def draft(self, text='Create a calendar event Dentist tomorrow at 2pm for 30 minutes', **kwargs):
        result = self.say(text, **kwargs)
        self.assertIn('Calendar draft (not created)', result)
        with self.actions.locked() as rows:
            row = next(r for r in rows.values() if r['state'] == 'draft')
        return row


class CalendarTests(CalendarFixture):
    def test_calendar_reads_recheck_saved_global_hold_before_auth_or_network(self):
        import chat_intent
        self.state = chat_intent.new_state()
        chat_intent.apply_turn(self.state, 'Hold all work', 'hold')
        with patch.object(self.client, 'configured') as configured, \
                patch.object(self.client, 'listing') as listing:
            for text in ('show my calendar today', 'calendar tomorrow', 'list calendar this week'):
                self.assertIn('On hold:', self.say(text))
            configured.assert_not_called()
            listing.assert_not_called()

    def test_defaults_and_supported_grammar(self):
        for text in ('Create a calendar event for 2am to go to bed',
                     'Please add a Google calendar event go to bed at 2am',
                     'Could you schedule a calendar event go to bed today at 2am'):
            event = event_spec(text, self.now)
            self.assertEqual(event['summary'], 'go to bed')
            self.assertEqual(event['start']['dateTime'], '2026-10-10T02:00:00-05:00')
            self.assertEqual(event['end']['dateTime'], '2026-10-10T03:00:00-05:00')
            self.assertEqual(event['reminders'], {'useDefault': False})
            self.assertEqual(event['visibility'], 'private')
            self.assertNotIn('attendees', event)
        self.now += 3600
        self.assertEqual(event_spec('Create a calendar event for 2am to go to bed', self.now)['start']['dateTime'],
                         '2026-10-11T02:00:00-05:00')

    def test_missing_ambiguous_past_dst_or_risky_input_never_creates(self):
        for clause in ('Dentist', 'Dentist next Tuesday', 'Dentist today at 1am',
                       'Dentist 2026-11-01 at 01:30', 'Dentist 2027-03-14 at 02:30',
                       'Dentist tomorrow at 25:00', 'Dentist tomorrow at 2pm for 0 minutes',
                       'Dentist tomorrow at 2pm for 25 hours', 'Dentist every day at 2pm',
                       'invite Alex tomorrow at 2pm', 'Dentist tomorrow at 2pm UTC',
                       'Dentist at 2pm tomorrow', 'Dentist 2028-01-01 at 2pm',
                       'Dentist next Tuesday at 2pm', 'Dentist tomorrow morning at 2pm',
                       'Dentist October 12 at 2pm', 'Dentist 10/12 at 2pm',
                       'Dentist UTC at 2pm', 'Dentist for 90 minutes tomorrow at 2pm'):
            with self.subTest(clause=clause):
                response = self.say('Create a calendar event ' + clause)
                self.assertNotIn('Calendar draft (not created)', response)
                self.assertFalse(self.client.creates)
        with self.actions.locked() as rows:
            self.assertEqual(rows, {})

    def test_quoted_title_can_contain_time_words_without_changing_schedule(self):
        event = event_spec('Create a calendar event "Friday planning" tomorrow at 2pm', self.now)
        self.assertEqual(event['summary'], 'Friday planning')
        self.assertEqual(event['start']['dateTime'], '2026-10-11T14:00:00-05:00')

    def test_needs_auth_no_fake_events_no_draft_no_network(self):
        self.client.error = NEEDS_AUTH
        self.assertEqual(self.say('show my calendar today'), NEEDS_AUTH)
        self.assertEqual(self.say('Create a calendar event Dentist tomorrow at 2pm'), NEEDS_AUTH)
        self.assertFalse(self.client.creates)
        self.assertFalse(self.client.reads)

    def test_draft_confirm_once_and_restart_persistence(self):
        row = self.draft()
        self.assertFalse(self.client.creates)
        self.assertIn('02:00 PM CDT', self.actions.receipt(row))
        self.assertIn('02:30 PM CDT', self.actions.receipt(row))
        self.actions = CalendarActions(self.root, self.client, lambda: self.now)
        reply = self.say('yes ' + row['token'])
        self.assertIn('Google Calendar confirmed event created: Dentist.', reply)
        self.assertEqual(len(self.client.creates), 1)
        self.actions = CalendarActions(self.root, self.client, lambda: self.now)
        self.assertEqual(self.say('yes ' + row['token']), reply)
        self.assertEqual(len(self.client.creates), 1)
        self.assertEqual(stat.S_IMODE((self.root / 'calendar/receipts.json').stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.root / 'calendar').stat().st_mode), 0o700)

    def test_receipt_claim_is_durable_before_external_write(self):
        row = self.draft()
        def create(event):
            rows = json.loads((self.root / 'calendar/receipts.json').read_text())
            self.assertEqual(rows[row['token']]['state'], 'claimed')
            return dict(event, status='confirmed')
        self.client.create = Mock(side_effect=create)
        self.assertIn('confirmed event created', self.say('yes ' + row['token']))
        self.client.create.assert_called_once()

    def test_ambiguous_failures_never_claim_success_or_retry(self):
        for result in (None, {}, {'id': 'wrong', 'status': 'confirmed'}, {'status': 'cancelled'}):
            row = self.draft()
            self.client.create = Mock(return_value=result)
            self.assertEqual(self.say('yes ' + row['token']), UNCERTAIN)
            restored = CalendarActions(self.root, self.client, lambda: self.now)
            self.assertEqual(restored.handle('yes ' + row['token'], 'chat', 'new', self.state), UNCERTAIN)
            self.client.create.assert_called_once()
        row = self.draft()
        self.client.create = Mock(side_effect=TimeoutError('secret remote URL'))
        self.assertEqual(self.say('yes ' + row['token']), UNCERTAIN)
        self.assertEqual(self.say('yes ' + row['token']), UNCERTAIN)
        self.client.create.assert_called_once()

    def test_wrong_event_content_and_missing_time_never_verify(self):
        for change in ({'summary': 'Other'}, {'start': {}}, {'attendees': [{'email': 'other@example.test'}]}):
            row = self.draft()
            self.client.create = Mock(return_value=dict(row['event'], status='confirmed', **change))
            self.assertEqual(self.say('yes ' + row['token']), UNCERTAIN)

    def test_expired_remote_auth_is_visible_and_confirmation_stays_consumed(self):
        row = self.draft()
        self.client.create = Mock(side_effect=CalendarError('Google Calendar needs auth: access was denied.'))
        response = self.say('yes ' + row['token'])
        self.assertIn('needs auth', response)
        self.assertIn('unconfirmed', response)
        self.assertEqual(self.say('yes ' + row['token']), response)
        self.client.create.assert_called_once()

    def test_concurrent_confirmations_submit_only_once(self):
        row = self.draft()
        other = CalendarActions(self.root, self.client, lambda: self.now)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda actions: actions.handle('yes ' + row['token'], 'chat',
                               str(uuid.uuid4()), self.state), (self.actions, other)))
        self.assertEqual(results[0], results[1])
        self.assertIn('confirmed event created', results[0])
        self.assertEqual(len(self.client.creates), 1)

    def test_crash_after_claim_and_failed_storage_never_repeat(self):
        row = self.draft()
        with self.actions.locked() as rows:
            rows[row['token']]['state'] = 'claimed'
            self.actions.save(rows)
        self.assertEqual(self.say('yes ' + row['token']), UNCERTAIN)
        self.assertFalse(self.client.creates)
        row = self.draft()
        with patch.object(self.actions, 'save', side_effect=OSError('disk full')):
            self.assertNotIn('confirmed event created', self.say('yes ' + row['token']))
        self.assertFalse(self.client.creates)

    def test_clock_time_draft_expires_when_start_passes(self):
        row = self.draft('Create a calendar event for 2am to go to bed')
        self.now += 14 * 60
        self.assertIn('expired', self.say('yes ' + row['token']))
        self.assertFalse(self.client.creates)

    def test_failed_receipt_save_after_api_confirmation_stays_uncertain(self):
        row = self.draft()
        save = self.actions.save
        count = [0]
        def fail_second(rows):
            count[0] += 1
            if count[0] == 2:
                raise OSError('disk full')
            save(rows)
        with patch.object(self.actions, 'save', side_effect=fail_second):
            self.assertIn('unconfirmed', self.say('yes ' + row['token']))
        self.assertEqual(self.say('yes ' + row['token']), UNCERTAIN)
        self.assertEqual(len(self.client.creates), 1)

    def test_confirmation_bound_to_conversation_separate_request_and_exact_token(self):
        row = self.draft(request_id='original')
        for message in ('yes', 'yes ' + row['token'] + ' and invite Alex', 'yes wbcal-wrong'):
            self.say(message)
        self.assertIn('No matching', self.say('yes ' + row['token'], cid='different'))
        self.assertIn('separate message', self.say('yes ' + row['token'], request_id='original'))
        self.assertFalse(self.client.creates)
        self.assertIn('confirmed event created', self.say('yes ' + row['token']))

    def test_cancel_replace_expire_and_reused_request_id(self):
        row = self.draft(request_id='first')
        self.assertEqual(self.say(row['text'], request_id='first'), self.actions.receipt(row))
        self.assertIn('different draft', self.say(row['text'] + ' extra', request_id='first'))
        replacement = self.draft()
        self.assertIn('replaced', self.say('yes ' + row['token']))
        self.assertIn('cancelled', self.say('cancel ' + replacement['token']))
        self.say('yes ' + replacement['token'])
        row = self.draft()
        self.now += 3601
        self.assertIn('expired', self.say('yes ' + row['token']))
        self.assertFalse(self.client.creates)

    def test_list_real_response_empty_all_day_timezone_and_pagination(self):
        self.client.response = {'items': [
            {'summary': 'Dentist', 'start': {'dateTime': '2026-10-10T19:00:00Z'}},
            {'summary': 'Birthday', 'start': {'date': '2026-10-10'}},
            {'status': 'cancelled'}], 'nextPageToken': 'more'}
        response = self.say("what's on my calendar today?")
        self.assertIn('02:00 PM CDT: Dentist', response)
        self.assertIn('Oct 10, 2026 (all day): Birthday', response)
        self.assertIn('first page', response)
        self.assertEqual(self.client.reads[-1], ('2026-10-10T00:00:00-05:00', '2026-10-11T00:00:00-05:00'))
        self.client.response = {'items': []}
        self.assertIn('No events returned', self.say('calendar tomorrow'))
        self.assertEqual(self.client.reads[-1][0], '2026-10-11T00:00:00-05:00')
        self.say('calendar this week')
        self.assertEqual(self.client.reads[-1], ('2026-10-05T00:00:00-05:00', '2026-10-12T00:00:00-05:00'))
        self.say('calendar on 2026-11-01')
        self.assertEqual(self.client.reads[-1], ('2026-11-01T00:00:00-05:00', '2026-11-02T00:00:00-06:00'))
        self.assertFalse(self.client.creates)

    def test_invalid_or_failed_read_is_not_an_empty_calendar(self):
        for response in ({}, {'items': 'bad'}, {'items': [{}]}, {'items': [{'start': {'dateTime': '2026-10-10T01:00'}}]}):
            self.client.response = response
            result = self.say('calendar')
            self.assertIn('no listing was verified', result)
            self.assertNotIn('No events', result)
        self.client.listing = Mock(side_effect=CalendarError('Google Calendar needs auth'))
        self.assertIn('needs auth', self.say('calendar'))

    def test_symlink_and_corrupt_storage_fail_closed(self):
        self.root.joinpath('calendar').mkdir()
        target = self.root / 'target'
        target.write_text('{}')
        path = self.root / 'calendar/receipts.json'
        path.symlink_to(target)
        self.assertIn('storage needs repair', self.say('create a calendar event Dentist tomorrow at 2pm'))
        self.assertEqual(target.read_text(), '{}')
        path.unlink()
        path.write_text('bad JSON')
        self.assertIn('could not finish', self.say('create a calendar event Dentist tomorrow at 2pm'))
        self.assertFalse(self.client.creates)


class CancellationTests(CalendarFixture):
    def preview(self, **kwargs):
        result = self.say('cancel calendar event ID event123', **kwargs)
        self.assertIn('Calendar cancellation preview (not cancelled)', result)
        with self.actions.locked() as rows:
            return next(r for r in rows.values() if r['state'] == 'draft')

    def test_exact_preview_durable_claim_receipt_restart_and_no_resend(self):
        row = self.preview(request_id='original')
        preview = self.actions.receipt(row)
        for field in ('Dentist', '2026-10-11T14:00:00-05:00', 'event123', '"v7"', 'five minutes'):
            self.assertIn(field, preview)
        self.client.delete.assert_not_called()

        def delete(event_id, etag):
            saved = json.loads((self.root / 'calendar/receipts.json').read_text())[row['token']]
            self.assertEqual(saved['state'], 'claimed')
            self.assertEqual((saved['cid'], saved['event']['id'], saved['event']['etag']), ('chat', event_id, etag))
            self.assertEqual(saved['approved_request_id'], 'approval')
            self.assertEqual(saved['consumed_at'], self.now)
            return {'http_status': 204}

        self.client.delete.side_effect = delete
        reply = self.say('yes ' + row['token'], request_id='approval')
        self.assertIn('confirmed event cancelled (DELETE HTTP 204)', reply)
        self.assertNotIn('cancelled at', reply)  # No fabricated server timestamp.
        self.client.delete.assert_called_once_with('event123', '"v7"')
        self.actions = CalendarActions(self.root, self.client, lambda: self.now)
        self.assertEqual(self.say('yes ' + row['token']), reply)
        self.assertEqual(self.say(row['text'], request_id='original'), reply)
        self.assertIn('consumed cancellation', self.say(row['text']))
        self.client.delete.assert_called_once()
        self.assertFalse(self.client.creates)

    def test_invalid_selection_never_fetches_or_creates_a_token(self):
        for tail in ('', 'Dentist', 'ID one two', 'ID ../event123', 'ID https://example.test',
                     'ID event123?sendUpdates=all', 'ID event123 and invite Alex'):
            with self.subTest(tail=tail):
                self.assertIn('one explicit event ID', self.say('cancel calendar event ' + tail))
        self.client.get.assert_not_called()
        self.client.delete.assert_not_called()

    def test_unsupported_and_malformed_events_fail_closed(self):
        original = copy.deepcopy(self.client.event)
        for change in ({'attendees': [{'email': 'other@example.test'}]}, {'attendeesOmitted': True},
                       {'recurrence': ['RRULE:FREQ=WEEKLY']}, {'recurringEventId': 'series'},
                       {'originalStartTime': {'date': '2026-10-11'}}, {'visibility': 'default'},
                       {'visibility': 'public'}, {'organizer': {'self': False}}, {'organizer': None},
                       {'eventType': 'outOfOffice'}, {'id': 'different'}, {'status': 'cancelled'},
                       {'etag': None}, {'etag': '*'}, {'etag': 'W/"v7"'}, {'etag': '"a", "b"'},
                       {'etag': '"v7"\r\nInjected: true'}, {'start': {}}, {'summary': []},
                       {'start': {'dateTime': '2026-10-11T14:00:00'}}):
            with self.subTest(change=change):
                self.client.event = dict(original, **change)
                reply = self.say('cancel calendar event ID event123')
                self.assertIn('Nothing cancelled', reply)
                self.assertNotIn('yes wbcal-', reply)
        with self.actions.locked() as rows:
            self.assertEqual(rows, {})
        self.client.delete.assert_not_called()

    def test_all_day_preview_and_minimal_persisted_data(self):
        self.client.event.update(start={'date': '2026-10-11'}, end={'date': '2026-10-12'},
                                 description='untrusted hidden data', location='not needed')
        row = self.preview()
        self.assertIn('2026-10-11 to 2026-10-12', self.actions.receipt(row))
        self.assertEqual(set(row['event']), {'id', 'etag', 'summary', 'start', 'end'})
        self.assertNotIn('hidden data', (self.root / 'calendar/receipts.json').read_text())

    def test_non_exact_yes_wrong_conversation_and_same_request_do_not_consume(self):
        row = self.preview(request_id='original')
        for message in ('yes', 'maybe', 'later', 'sure?', 'I think so', '',
                        'yes ' + row['token'] + ' and delete another', 'yes wbcal-wrong'):
            self.say(message)
        self.assertIn('No matching', self.say('yes ' + row['token'], cid='different'))
        self.assertIn('separate message', self.say('yes ' + row['token'], request_id='original'))
        self.client.delete.assert_not_called()
        with self.actions.locked() as rows:
            self.assertEqual(rows[row['token']]['state'], 'draft')
        self.assertIn('confirmed event cancelled', self.say('yes ' + row['token']))

    def test_duplicate_preview_is_stable_and_request_id_cannot_select_another_event(self):
        row = self.preview(request_id='original')
        self.now += 100
        self.assertEqual(self.say(row['text'], request_id='original'), self.actions.receipt(row))
        self.assertIn('different draft', self.say('cancel calendar event ID different', request_id='original'))
        self.client.get.assert_called_once_with('event123')
        self.client.delete.assert_not_called()

    def test_discard_replace_and_expire_at_exact_boundary(self):
        row = self.preview()
        self.assertIn('discarded', self.say('cancel ' + row['token']))
        self.say('yes ' + row['token'])
        row = self.preview()
        replacement = self.preview()
        self.assertIn('replaced', self.say('yes ' + row['token']))
        self.now = replacement['expires']
        self.assertIn('expired', self.say('yes ' + replacement['token']))
        self.client.delete.assert_not_called()

    def test_expiry_during_revalidation_never_deletes(self):
        row = self.preview()
        def get(_event_id):
            self.now = row['expires']
            return copy.deepcopy(self.client.event)
        self.client.get.side_effect = get
        self.assertIn('expired', self.say('yes ' + row['token']))
        self.client.delete.assert_not_called()

    def test_global_and_project_holds_at_admission_and_execution(self):
        import chat_intent
        for hold in ('Hold all work', 'Hold WebBob'):
            with self.subTest(hold=hold):
                self.state = chat_intent.new_state()
                chat_intent.apply_turn(self.state, hold, 'hold')
                self.client.get.reset_mock()
                with patch.object(self.client, 'configured') as configured:
                    self.assertIn('On hold:', self.say('cancel calendar event ID event123'))
                    configured.assert_not_called()
                self.client.get.assert_not_called()
                self.state = chat_intent.new_state()
                self.client.event['summary'] = 'WebBob review'
                row = self.preview()
                chat_intent.apply_turn(self.state, hold, 'hold')
                before = copy.deepcopy(self.state)
                self.client.get.reset_mock()
                self.assertIn('On hold:', self.say('yes ' + row['token']))
                self.client.get.assert_not_called()
                self.assertEqual(self.state, before)
        self.client.delete.assert_not_called()

    def test_hold_applied_during_fetch_or_claim_save_blocks_delete(self):
        import chat_intent
        row = self.preview()
        def get(_event_id):
            chat_intent.apply_turn(self.state, 'Hold all work', 'hold')
            return copy.deepcopy(self.client.event)
        self.client.get.side_effect = get
        self.assertIn('On hold:', self.say('yes ' + row['token']))
        self.state = chat_intent.new_state()
        self.client.get.side_effect = lambda _id: copy.deepcopy(self.client.event)
        save = self.actions.save
        def save_and_hold(rows):
            save(rows)
            chat_intent.apply_turn(self.state, 'Hold all work', 'hold')
        with patch.object(self.actions, 'save', side_effect=save_and_hold):
            self.assertIn('On hold:', self.say('yes ' + row['token']))
        self.client.delete.assert_not_called()

    def test_changed_event_or_new_attendees_or_recurrence_invalidates_token(self):
        original = copy.deepcopy(self.client.event)
        for change in ({'etag': '"v8"'}, {'summary': 'Different'},
                       {'attendees': [{'email': 'other@example.test'}]},
                       {'recurringEventId': 'series'}, {'visibility': 'public'}):
            with self.subTest(change=change):
                self.client.event = copy.deepcopy(original)
                row = self.preview()
                self.client.event.update(change)
                reply = self.say('yes ' + row['token'])
                self.assertIn('fresh preview', reply)
                self.client.event = copy.deepcopy(original)
                self.assertEqual(self.say('yes ' + row['token']), reply)
        self.client.delete.assert_not_called()

    def test_concurrent_confirmations_across_instances_and_conversations_delete_once(self):
        # Separate previews in two conversations cannot authorize two attempts.
        first = self.preview()
        self.say(first['text'], cid='other')
        with self.actions.locked() as rows:
            second = next(r for r in rows.values() if r['cid'] == 'other')
        other = CalendarActions(self.root, self.client, lambda: self.now)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda args: args[0].handle('yes ' + args[1]['token'], args[1]['cid'],
                                  str(uuid.uuid4()), self.state),
                                  ((self.actions, first), (other, first), (other, second))))
        self.assertTrue(any('confirmed event cancelled' in r for r in results))
        self.client.delete.assert_called_once_with('event123', '"v7"')

    def test_failed_preview_or_claim_save_never_deletes(self):
        with patch.object(self.actions, 'save', side_effect=OSError('fixture disk error')):
            self.assertNotIn('yes wbcal-', self.say('cancel calendar event ID event123'))
        row = self.preview()
        with patch.object(self.actions, 'save', side_effect=OSError('fixture disk error')):
            self.assertIn('could not finish', self.say('yes ' + row['token']))
        self.client.delete.assert_not_called()

    def test_crash_after_claim_cannot_rearm_after_restart(self):
        row = self.preview()
        with self.actions.locked() as rows:
            rows[row['token']]['state'] = 'claimed'
            self.actions.save(rows)
        self.actions = CalendarActions(self.root, self.client, lambda: self.now)
        self.assertEqual(self.say('yes ' + row['token']), CANCEL_UNCERTAIN)
        self.assertIn('consumed cancellation', self.say(row['text'], cid='other'))
        self.client.delete.assert_not_called()

    def test_failed_final_save_leaves_durable_claim_and_never_retries(self):
        row = self.preview()
        save = self.actions.save
        calls = []
        def save_once(rows):
            calls.append(True)
            if len(calls) > 1:
                raise OSError('fixture disk error')
            save(rows)
        with patch.object(self.actions, 'save', side_effect=save_once):
            self.assertIn('unconfirmed', self.say('yes ' + row['token']))
        self.actions = CalendarActions(self.root, self.client, lambda: self.now)
        self.assertEqual(self.say('yes ' + row['token']), CANCEL_UNCERTAIN)
        self.client.delete.assert_called_once()

    def test_timeout_followed_by_404_is_ambiguous_sanitized_and_never_retried(self):
        row = self.preview()
        self.client.get.side_effect = [copy.deepcopy(self.client.event), CalendarHTTPError(404)]
        self.client.delete.side_effect = TimeoutError('Bearer fixture-secret remote-url')
        with patch('logging.Logger._log') as log:
            reply = self.say('yes ' + row['token'])
            log.assert_not_called()
        self.assertIn(CANCEL_UNCERTAIN, reply)
        self.assertIn('follow-up GET returned HTTP 404', reply)
        self.assertNotIn('confirmed event cancelled', reply)
        self.assertNotIn('fixture-secret', reply + (self.root / 'calendar/receipts.json').read_text())
        self.actions = CalendarActions(self.root, self.client, lambda: self.now)
        self.assertEqual(self.say('yes ' + row['token']), reply)
        self.assertIn('consumed cancellation', self.say(row['text']))
        self.client.delete.assert_called_once()

    def test_unverified_delete_responses_never_claim_success(self):
        for response in (None, {}, {'status': 'cancelled'}, {'http_status': 200}, {'http_status': '204'}):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as folder:
                self.actions = CalendarActions(folder, self.client, lambda: self.now)
                row = self.preview()
                self.client.delete.reset_mock()
                self.client.delete.return_value = response
                reply = self.say('yes ' + row['token'])
                self.assertIn(CANCEL_UNCERTAIN, reply)
                self.assertEqual(self.say('yes ' + row['token']), reply)
                self.client.delete.assert_called_once()

    def test_if_match_race_rejection_does_not_claim_cancellation_or_retry(self):
        row = self.preview()
        self.client.delete.side_effect = CalendarHTTPError(412)
        reply = self.say('yes ' + row['token'])
        self.assertIn('changed event (HTTP 412)', reply)
        self.assertNotIn('confirmed event cancelled', reply)
        self.assertEqual(self.say('yes ' + row['token']), reply)
        self.client.delete.assert_called_once_with('event123', '"v7"')


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'oauth.json'
        self.path.write_text(json.dumps(dict(type='authorized_user', client_id='client', client_secret='private', refresh_token='refresh')))
        self.path.chmod(0o600)
        self.transport = Mock(side_effect=[{'access_token': 'access'}, {'items': []}])
        self.client = GoogleCalendar(self.path, self.transport)

    def test_default_credentials_discovery_and_explicit_override(self):
        home = self.path.parent
        default = home / '.config/webbob/google-calendar.json'
        default.parent.mkdir(parents=True)
        self.path.rename(default)
        client = GoogleCalendar(transport=self.transport)
        with patch('calendar_actions.Path.home', return_value=home), patch.dict(os.environ, {}, clear=True):
            client.configured()
            adc = home / '.config/gcloud/application_default_credentials.json'
            adc.parent.mkdir(parents=True)
            default.rename(adc)
            client.configured()
            with patch.dict(os.environ, {'BOB_GOOGLE_CALENDAR_CREDENTIALS': str(self.path)}):
                with self.assertRaisesRegex(CalendarError, 'needs auth'):
                    client.configured()
        self.transport.assert_not_called()

    def test_existing_bluebubbles_helper_reads_with_injected_http_boundary(self):
        db = self.path.parent / 'bluebubbles.db'
        with sqlite3.connect(db) as connection:
            connection.execute('CREATE TABLE config (name TEXT, value TEXT)')
            connection.executemany('INSERT INTO config VALUES (?, ?)',
                                   [('password', 'fixture-password'), ('socket_port', '1234')])
        helper = BlueBubbles(db)
        thread = dict(guid='iMessage;-;+15550101010', participants=[{'address': '+15550101010'}])
        message = dict(text='Existing helper message', isFromMe=False)
        with patch('texting.request_json', side_effect=[{'data': [thread]}, {'data': [message]}]) as http:
            self.assertEqual(helper.chats(), [thread])
            self.assertEqual(helper.messages(thread['guid']), [message])
            chats, messages = http.call_args_list
            self.assertEqual(chats.args[0], 'http://127.0.0.1:1234')
            self.assertTrue(chats.args[1].startswith('/api/v1/chat/query?'))
            self.assertEqual(chats.kwargs['data']['limit'], 200)
            self.assertIn('/message?', messages.args[1])
            self.assertIsNone(messages.kwargs['data'])
            with self.assertRaisesRegex(TextingError, 'not a permitted read'):
                helper._read('/message/text', {'text': 'must not send'})
            self.assertEqual(http.call_count, 2)

    def test_credentials_are_read_lazily_and_oauth_is_injected(self):
        self.client.configured()
        self.transport.assert_not_called()
        self.assertEqual(self.client.listing('start', 'end'), {'items': []})
        oauth, listing = self.transport.call_args_list
        self.assertEqual(oauth.args[0], 'https://oauth2.googleapis.com/token')
        self.assertEqual(oauth.kwargs['data']['grant_type'], 'refresh_token')
        self.assertEqual(listing.kwargs['headers'], {'Authorization': 'Bearer access'})
        self.assertIn('timeZone=America%2FChicago', listing.args[0])
        self.assertEqual(self.path.read_text().count('refresh'), 2)

    def test_missing_access_token_and_non_json_responses_never_verify(self):
        self.transport.side_effect = [{}]
        with self.assertRaisesRegex(CalendarError, 'needs auth'):
            self.client.listing('start', 'end')
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch('calendar_actions.urllib.request.build_opener', return_value=opener):
            for raw in (b'not json', b'[]', b'x' * (2 * 1024 * 1024 + 1)):
                response.read.return_value = raw
                with self.assertRaisesRegex(CalendarError, 'no success was verified'):
                    request_json('https://www.googleapis.com/calendar/v3/calendars/primary/events')

    def test_create_uses_primary_no_updates_and_exact_payload(self):
        self.transport.side_effect = [{'access_token': 'access'}, {'id': 'receipt'}]
        event = {'id': 'test', 'summary': 'Test'}
        self.assertEqual(self.client.create(event), {'id': 'receipt'})
        request = self.transport.call_args
        self.assertEqual(request.args[0], 'https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=none')
        self.assertEqual(request.kwargs['data'], event)

    def test_cancellation_uses_injected_get_delete_and_conditional_version_only(self):
        event = FakeCalendar().event
        self.transport.side_effect = [
            {'access_token': 'access'}, event, {'access_token': 'access'}, event,
            {'access_token': 'access'}, {'http_status': 204}]
        actions = CalendarActions(self.path.parent, self.client, lambda: 1000)
        state = {'holds': {}, 'last_permission': None}
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Network forbidden')):
            preview = actions.handle('cancel calendar event ID event123', 'chat', 'draft', state)
            with actions.locked() as rows:
                row, = rows.values()
            self.assertIn('not cancelled', preview)
            reply = actions.handle('yes ' + row['token'], 'chat', 'approve', state)
            self.assertIn('confirmed event cancelled', reply)
            self.assertEqual(actions.handle('yes ' + row['token'], 'chat', 'again', state), reply)
        requests = [c for c in self.transport.call_args_list if '/calendar/v3/' in c.args[0]]
        self.assertEqual(len(requests), 3)
        self.assertEqual([c.kwargs.get('method', 'GET') for c in requests], ['GET', 'GET', 'DELETE'])
        self.assertEqual(requests[0].args[0], 'https://www.googleapis.com/calendar/v3/calendars/primary/events/event123')
        self.assertEqual(requests[1].args, requests[0].args)
        deletion = requests[2]
        self.assertEqual(deletion.args[0], requests[0].args[0] + '?sendUpdates=none')
        self.assertEqual(deletion.kwargs['headers'], {'Authorization': 'Bearer access', 'If-Match': '"v7"'})
        self.assertNotIn('data', deletion.kwargs)
        persisted = (actions.folder / 'receipts.json').read_text()
        for forbidden in ('Bearer ', 'access_token', 'refresh_token', 'client_secret'):
            self.assertNotIn(forbidden, preview + reply + persisted)

    def test_delete_transport_accepts_only_observed_empty_204(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status = 204
        opener = Mock()
        opener.open.return_value = response
        url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events/event123?sendUpdates=none'
        with patch('calendar_actions.urllib.request.build_opener', return_value=opener):
            self.assertEqual(request_json(url, method='DELETE', headers={'If-Match': '"v7"'}), {'http_status': 204})
            req = opener.open.call_args.args[0]
            self.assertEqual(req.get_method(), 'DELETE')
            self.assertEqual(req.get_header('If-match'), '"v7"')
            self.assertIsNone(req.data)
            response.read.assert_not_called()
            for status in (200, 202, 404):
                response.status = status
                with self.assertRaises(CalendarError):
                    request_json(url, method='DELETE')
            for status in (404, 410, 412, 500):
                opener.open.reset_mock()
                opener.open.side_effect = urllib.error.HTTPError('fixture-secret', status, 'fixture-secret', {}, io.BytesIO())
                with self.assertRaises(CalendarHTTPError) as error:
                    request_json(url, method='DELETE')
                self.assertEqual(error.exception.status, status)
                self.assertNotIn('fixture-secret', str(error.exception))
                opener.open.assert_called_once()
            opener.open.reset_mock()
            opener.open.side_effect = TimeoutError('fixture-secret')
            with self.assertRaises(CalendarError) as error:
                request_json(url, method='DELETE')
            self.assertNotIn('fixture-secret', str(error.exception))
            opener.open.assert_called_once()

    def test_invalid_event_id_is_rejected_before_auth_or_transport(self):
        for event_id in ('../event', 'event?sendUpdates=all', 'event/extra', '', 'https://host/event'):
            with self.assertRaises(CalendarError):
                self.client.get(event_id)
            with self.assertRaises(CalendarError):
                self.client.delete(event_id, '"v7"')
        self.transport.assert_not_called()

    def test_missing_insecure_symlink_invalid_and_service_credentials_need_auth(self):
        for value in ({}, {'type': 'service_account'}, [], {'client_id': 'secret'}):
            self.path.write_text(json.dumps(value))
            with self.assertRaisesRegex(CalendarError, 'needs auth'):
                self.client.configured()
        self.path.chmod(0o644)
        with self.assertRaisesRegex(CalendarError, 'needs auth'):
            self.client.configured()
        self.path.unlink()
        with self.assertRaisesRegex(CalendarError, 'needs auth'):
            self.client.configured()
        self.path.symlink_to(self.path.parent / 'absent')
        with self.assertRaisesRegex(CalendarError, 'needs auth'):
            self.client.configured()
        self.transport.assert_not_called()

    def test_transport_is_bounded_no_proxy_no_redirect_no_retry_and_sanitizes_errors(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"items": []}'
        opener = Mock()
        opener.open.return_value = response
        with patch('calendar_actions.urllib.request.build_opener', return_value=opener) as factory:
            self.assertEqual(request_json('https://www.googleapis.com/calendar/v3/calendars/primary/events'), {'items': []})
            self.assertEqual(factory.call_args.args[0].proxies, {})
            self.assertEqual(opener.open.call_args.kwargs['timeout'], 10)
            self.assertEqual(response.read.call_args.args, (2 * 1024 * 1024 + 1,))
            with self.assertRaises(CalendarError):
                factory.call_args.args[1].redirect_request(None)
            for status in (401, 403, 500):
                opener.open.side_effect = urllib.error.HTTPError('secret-url', status, 'secret-body', {}, io.BytesIO())
                with self.assertRaises(CalendarError) as error:
                    request_json('https://www.googleapis.com/calendar/v3/calendars/primary/events')
                self.assertNotIn('secret', str(error.exception))
                if status in (401, 403):
                    self.assertIn('needs auth', str(error.exception))
        with self.assertRaises(CalendarError):
            request_json('http://attacker.invalid')


class RoutingTests(CalendarFixture):
    def setUp(self):
        super().setUp()
        self.providers = OfflineProviders()
        self.bluebubbles = Mock()
        self.bluebubbles.chats.return_value = [dict(guid='iMessage;-;+15550101010', displayName='Alex Morgan',
            participants=[{'address': '+15550101010'}])]
        self.bluebubbles.messages.return_value = [dict(text='Actual helper text', isFromMe=False, dateCreated=1791612000000)]
        self.andrea = Mock()
        self.andrea.prepare.return_value = None
        self.texting = Texting(self.bluebubbles, self.andrea, clock=lambda: self.now)
        self.chat = Chat(self.root / 'chat', self.root, self.providers, texting=self.texting,
                         reminder_notifier=Mock(), calendar=self.actions)
        self.addCleanup(self.chat.close)
        self.cid = self.chat.new_conversation()['id']

    def submit(self, text):
        with patch('app.parse_work', side_effect=AssertionError('Entered generic queue')):
            return self.chat.submit(self.cid, text, str(uuid.uuid4()), actor='owner')['messages'][-1]

    def test_calendar_create_read_confirm_are_direct(self):
        response = self.submit('Create a calendar event Dentist tomorrow at 2pm')
        self.assertEqual(response['provider'], 'calendar')
        with self.actions.locked() as rows:
            row, = rows.values()
        self.assertIn('confirmed event created', self.submit('yes ' + row['token'])['content'])
        self.assertIn('No events returned', self.submit('show my calendar today')['content'])
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))

    def test_calendar_cancel_preview_and_exact_confirmation_are_direct(self):
        response = self.submit('cancel calendar event ID event123')
        self.assertEqual(response['provider'], 'calendar')
        self.assertIn('not cancelled', response['content'])
        self.client.delete.assert_not_called()
        with self.actions.locked() as rows:
            row, = rows.values()
        result = self.submit('yes ' + row['token'])
        self.assertEqual(result['provider'], 'calendar')
        self.assertIn('confirmed event cancelled', result['content'])
        self.client.delete.assert_called_once_with('event123', '"v7"')
        self.assertFalse(self.providers.calls)
        self.assertFalse(task_queue.tasks(self.root))
        self.andrea.deliver.assert_not_called()
        self.chat.reminder_notifier.assert_not_called()

    def test_saved_hold_blocks_cancellation_confirmation_and_new_preview(self):
        self.client.event['summary'] = 'WebBob review'
        self.submit('cancel calendar event ID event123')
        with self.actions.locked() as rows:
            row, = rows.values()
        self.chat.submit(self.cid, 'Hold WebBob', str(uuid.uuid4()))
        before = copy.deepcopy(self.chat.get(self.cid)['intent_state'])
        self.assertIn('On hold:', self.submit('yes ' + row['token'])['content'])
        self.assertIn('On hold:', self.submit('cancel calendar event ID event123')['content'])
        self.assertEqual(self.chat.get(self.cid)['intent_state'], before)
        self.client.delete.assert_not_called()
        self.assertFalse(self.providers.calls)

    def test_needs_auth_is_direct_and_never_fabricates_events(self):
        self.client.error = NEEDS_AUTH
        for text in ('Create a calendar event Dentist tomorrow at 2pm', 'calendar today'):
            self.assertEqual(self.submit(text)['content'], NEEDS_AUTH)
        self.assertFalse(self.providers.calls)

    def test_saved_global_and_project_holds_block_drafts_and_confirmation(self):
        for hold, title in [('Hold all work', 'Dentist'), ('Hold WebBob', 'WebBob review')]:
            self.cid = self.chat.new_conversation()['id']
            self.submit('Create a calendar event ' + title + ' tomorrow at 2pm')
            with self.actions.locked() as rows:
                row = next(r for r in rows.values() if r['cid'] == self.cid)
            self.chat.submit(self.cid, hold, str(uuid.uuid4()))
            before = copy.deepcopy(self.chat.get(self.cid)['intent_state'])
            self.assertIn('On hold:', self.submit('yes ' + row['token'])['content'])
            self.assertIn('On hold:', self.submit('Create a calendar event ' + title + ' tomorrow at 3pm')['content'])
            self.assertEqual(self.chat.get(self.cid)['intent_state'], before)
        self.assertFalse(self.client.creates)

    def test_pr1_2am_reminder_executes_directly(self):
        self.chat.reminders.clock = lambda: self.now
        response = self.submit('Create a reminder for 2am to go to bed')
        self.assertEqual(response['provider'], 'reminders')
        self.assertIn('Reminder saved: go to bed', response['content'])
        self.assertIn('Oct 10, 2026 at 02:00 AM CDT', response['content'])
        self.assertFalse(self.client.creates)
        self.assertFalse(self.providers.calls)
        self.chat.reminder_notifier.assert_not_called()

    def test_existing_text_helper_reads_are_read_only_and_sends_stay_drafts(self):
        self.assertIn('Alex Morgan', self.submit('texts')['content'])
        self.assertIn('Actual helper text', self.submit('read texts from Alex Morgan')['content'])
        self.assertIn('1 message', self.submit('summarize texts from Alex Morgan')['content'])
        response = self.submit('send a text to Alex Morgan: Hello')
        self.assertIn('text_draft', response)
        self.andrea.deliver.assert_not_called()
        self.submit('yes')
        self.andrea.deliver.assert_not_called()
        self.assertFalse(self.providers.calls)
        self.assertFalse(self.client.creates)
        self.assertFalse(task_queue.tasks(self.root))

    def test_text_helper_error_is_honest(self):
        self.bluebubbles.chats.side_effect = TextingError('BlueBubbles read configuration is unavailable. Nothing was sent.')
        self.assertIn('configuration is unavailable', self.submit('texts')['content'])
        self.andrea.deliver.assert_not_called()


if __name__ == '__main__':
    unittest.main()
